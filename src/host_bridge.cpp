#include "qarvtk/gl.hpp"
#include "qarvtk/host_bridge.h"
#include "qarvtk/host_frame_lease.hpp"
#include "qarvtk/host_stream_scheduler.hpp"
#include "qarvtk/host_panels.hpp"
#include "qarvtk/host_wgl.hpp"
#include "qarvtk/gl_copy.hpp"
#include "qarvtk/gl_composite.hpp"
#include "../apps/wgl_callbacks.hpp"
#include "../apps/legacy_peer_observer.hpp"
#include "../apps/legacy_frame_wait.hpp"
#include "../apps/host_config.hpp"
#include <array>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <memory>
#include <mutex>
#include <string>
#include <sstream>
#include <iomanip>
#include <thread>
#include <vector>

QAR_IMPLEMENT_DYNAMIC_LOADING()

namespace {
using Clock=std::chrono::steady_clock;
double milliseconds(Clock::time_point from,Clock::time_point to=Clock::now()){
  return std::chrono::duration<double,std::milli>(to-from).count();
}
struct FrameTimings {
  double host_sync{},composite{},copy{},copy_finish{};
  FrameTimings& operator+=(const FrameTimings& other){
    host_sync+=other.host_sync;composite+=other.composite;copy+=other.copy;copy_finish+=other.copy_finish;return *this;
  }
};
std::atomic<bool> active{false};
void message(char* target,uint32_t size,const std::string& text){
  if(target&&size){const auto count=std::min<std::size_t>(text.size(),size-1);std::memcpy(target,text.data(),count);target[count]=0;}
}
void checked(QarResult result,const char* operation){
  if(qar_result_is_success(result))return;
  char text[1024]{};qar_result_message(result,text,sizeof(text));
  throw std::runtime_error(std::string(operation)+" ("+std::to_string(result.code)+"): "+text);
}
bool extension(const char* wanted){
  GLint count=0;glGetIntegerv(GL_NUM_EXTENSIONS,&count);
  for(GLint i=0;i<count;++i){const auto* name=glGetStringi(GL_EXTENSIONS,i);if(name&&std::strcmp(reinterpret_cast<const char*>(name),wanted)==0)return true;}
  return false;
}
QarGraphicsDeviceId device(){
  if(!extension("GL_EXT_memory_object")||!extension("GL_EXT_memory_object_win32"))
    throw std::runtime_error("The host GPU does not expose Windows external-memory support required by QAROS");
  using GetBytes=void(APIENTRY*)(GLenum,GLubyte*);
  auto get=reinterpret_cast<GetBytes>(wglGetProcAddress("glGetUnsignedBytevEXT"));
  if(!get)throw std::runtime_error("Cannot query the host GPU LUID");
  auto id=qar_graphics_device_id_default();id.id_type=QAR_GPU_DEVICE_ID_TYPE_LUID;
  get(0x9599,reinterpret_cast<GLubyte*>(&id.luid));
  if(glGetError()!=GL_NO_ERROR)throw std::runtime_error("Host GPU identity query failed");
  return id;
}
qarvtk::Frame layout(const QarVideoFrameOpenGl& f){
  if(f.textures_count>QAR_MAX_FRAME_TEXTURES||f.texture_views_count>QAR_MAX_FRAME_VIEWS)
    throw std::runtime_error("Invalid SDK frame array sizes");
  qarvtk::Frame out;
  for(size_t i=0;i<f.textures_count;++i){const auto& t=f.textures[i];out.textures.push_back({t.texture,t.size.width,t.size.height,t.size.array_layers});}
  for(size_t i=0;i<f.texture_views_count;++i){
    const auto& v=f.texture_views[i];
    if(v.eye!=QAR_VIDEO_FRAME_VIEW_EYE_LEFT&&v.eye!=QAR_VIDEO_FRAME_VIEW_EYE_RIGHT)
      throw std::runtime_error("Host bridge requires separate left/right views");
    if(v.data_type!=QAR_VIDEO_FRAME_VIEW_TYPE_COLOR&&v.data_type!=QAR_VIDEO_FRAME_VIEW_TYPE_DEPTH)
      throw std::runtime_error("Invalid SDK frame plane");
    const bool depth=v.data_type==QAR_VIDEO_FRAME_VIEW_TYPE_DEPTH;
    if((!depth&&v.texture_format!=QAR_PIXEL_FORMAT_R8G8B8A8)||
       (depth&&v.texture_format!=QAR_PIXEL_FORMAT_D32_FLOAT&&v.texture_format!=QAR_PIXEL_FORMAT_R32_FLOAT))
      throw std::runtime_error("Unsupported SDK pixel format");
    out.views.push_back({v.eye==QAR_VIDEO_FRAME_VIEW_EYE_LEFT?qarvtk::Eye::left:qarvtk::Eye::right,
      depth?qarvtk::Plane::depth:qarvtk::Plane::color,v.texture_index,v.start_x,v.start_y,v.end_x,v.end_y,v.array_layer_index});
  }
  return out;
}
void on_peer(QarPeerSpec* spec,void* state) noexcept {
  QarPeerId id{};QarAppState app=QAR_APP_STATE_UNKNOWN;
  if(spec&&state&&qar_result_is_success(qar_peer_spec_get_id(spec,&id))&&qar_result_is_success(qar_peer_spec_get_app_state(spec,&app)))
    static_cast<qarvtk::LegacyPeerObserver*>(state)->record(id,app);
}
}

struct QarvtkHost {
  struct Volume {
    QarvtkHostPlacement placement{};
    std::string name;
    std::unique_ptr<qarvtk::HostSharedWgl> graphics;
    std::unique_ptr<qarvtk::WglCallbacks> callbacks;
  };
  const DWORD owner=GetCurrentThreadId();
  HGLRC host_context{};
  std::unique_ptr<qarvtk::HostSharedWgl> copying;
  std::unique_ptr<qarvtk::GlCopy> copier;
  std::unique_ptr<qarvtk::GlComposite> compositor;
  std::vector<Volume> volumes;
  std::unique_ptr<qarvtk::HostPanels> panels;
  QarGraphicsDeviceId adapter=qar_graphics_device_id_default();
  std::thread worker;
  std::mutex mutex,cancel_mutex;
  std::condition_variable condition;
  std::atomic<bool> stopping{false},done{false};
  QarCancelToken* operation{}; // Protected by cancel_mutex, destroyed before library unload.
  bool failed{};
  qarvtk::HostFrameLease lease;
  FrameTimings timings;
  const Clock::time_point created=Clock::now();
  uint64_t sent{};
  QarvtkHostFrame request{};
  qarvtk::Frame frame;
  std::array<qarvtk::EyeViews,2> views{};
  std::string status="Starting live Slicer transport",sdk_root,target,log_folder;
  std::ofstream log;

  ~QarvtkHost(){
    if(worker.joinable())worker.join();
    if(copying){
      try {qarvtk::WglBinding binding(*copying);compositor.reset();copier.reset();}
      catch(...){compositor.release();copier.release();} // Context destruction releases GL objects.
    }
  }
  void gui() const {if(GetCurrentThreadId()!=owner)throw std::runtime_error("Host API must run on its creating GUI thread");}
  void log_line(const std::string& text){ // mutex held by caller
    if(log)log<<"elapsed_ms="<<milliseconds(created)<<" "<<text<<std::endl;
  }
  void note(const std::string& text){std::lock_guard<std::mutex> lock(mutex);log_line(text);}
  void set_status(const std::string& text){
    std::lock_guard<std::mutex> lock(mutex);status=text;log_line(text);
  }
  void fail(const std::string& text){
    {std::lock_guard<std::mutex> lock(mutex);if(!failed){failed=true;status=text;log_line("ERROR: "+text);}lease.cancel();}
    stopping=true;condition.notify_all();
  }
  void stop(){
    gui();stopping=true;
    if(panels)panels->request_stop();
    {std::lock_guard<std::mutex> lock(mutex);lease.cancel();log_line("Stop requested by GUI");}
    condition.notify_all();
    std::lock_guard<std::mutex> lock(cancel_mutex);
    if(operation)qar_cancel_token_cancel(operation);
  }
  bool pause(std::chrono::milliseconds duration){
    std::unique_lock<std::mutex> lock(mutex);
    condition.wait_for(lock,duration,[&]{return stopping.load();});return !stopping;
  }
  void deadline(){
    std::lock_guard<std::mutex> lock(cancel_mutex);
    if(stopping)throw std::runtime_error("Live stream stopped");
    if(operation)qar_cancel_token_handle_destroy(operation);
    operation=nullptr;checked(qar_cancel_token_create_with_timeout(&operation,60000),"create SDK timeout");
  }
  void initialize(){
    gui();host_context=wglGetCurrentContext();const auto dc=wglGetCurrentDC();
    if(!host_context||!dc)throw std::runtime_error("Make the Slicer render window current before creating the host bridge");
    if(target!="visualizer"&&target!="quest")throw std::runtime_error("Host target must be visualizer or quest");
    const auto sdk=std::filesystem::u8path(sdk_root);
    if(!std::filesystem::is_regular_file(sdk/"bin"/"qar-streaming-c.dll"))throw std::runtime_error("Missing complete QAROS session runtime");
    std::filesystem::create_directories(std::filesystem::u8path(log_folder));
    log.open(std::filesystem::u8path(log_folder)/"host-bridge.log",std::ios::app);
    if(!log)throw std::runtime_error("Cannot open host bridge log");
    copying=std::make_unique<qarvtk::HostSharedWgl>(dc,host_context);
    {
      qarvtk::WglBinding binding(*copying);qarvtk::hostgl::load();adapter=device();
      copier=std::make_unique<qarvtk::GlCopy>();compositor=std::make_unique<qarvtk::GlComposite>();
      log<<"Host GPU: "<<glGetString(GL_VENDOR)<<" / "<<glGetString(GL_RENDERER)<<" / "<<glGetString(GL_VERSION)<<std::endl;
    }
    // SDK senders may invoke graphics callbacks concurrently. Give each its
    // own context, all sharing Slicer's objects, instead of competing for one.
    for(auto& volume:volumes){
      volume.graphics=std::make_unique<qarvtk::HostSharedWgl>(dc,host_context);
      volume.callbacks=std::make_unique<qarvtk::WglCallbacks>(volume.graphics->dc,volume.graphics->context);
      const auto probe=volume.callbacks->probe_on_worker();
      if(!probe.get_string_i||!probe.memory_import)throw std::runtime_error("Shared SDK context lacks required OpenGL interop functions");
    }
    panels=std::make_unique<qarvtk::HostPanels>([this](const std::string& text){note(text);});
    worker=std::thread([this]{run();});
  }
  void run() noexcept;
  void copy(uint64_t serial,unsigned eye,qarvtk::RenderedEye source,bool depth,unsigned vc=0,unsigned vd=0){
    gui();
    if(wglGetCurrentContext()!=host_context)throw std::runtime_error("Slicer changed the host OpenGL context; restart streaming");
    std::lock_guard<std::mutex> lock(mutex);
    if(stopping)throw std::runtime_error("Invalid or expired host frame lease");
    lease.check_plane(serial,eye,depth);
    if(!source.width||!source.height||source.width>request.eyes[eye].width||source.height>request.eyes[eye].height)
      throw std::runtime_error("Host render size must be positive and no larger than the requested eye");
    auto stamp=Clock::now();
    glFinish(); // Complete host writes before the sharing context reads them.
    timings.host_sync+=milliseconds(stamp);
    qarvtk::WglBinding binding(*copying);
    if((vc==0)!=(vd==0))throw std::runtime_error("Incomplete volume depth textures");
    if(depth&&vc){
      stamp=Clock::now();
      if(!glIsTexture(vc)||!glIsTexture(vd))throw std::runtime_error("Volume textures are not shared");
      source=compositor->combine(source,vc,vd);
      timings.composite+=milliseconds(stamp);
    }
    stamp=Clock::now();
    copier->copy_plane(source,frame,views[eye],depth);
    timings.copy+=milliseconds(stamp);stamp=Clock::now();
    copier->finish(); // Borrowed host textures may be overwritten immediately.
    timings.copy_finish+=milliseconds(stamp);
    lease.complete_plane(serial,eye,depth);
  }
};

namespace {
// All SDK control operations are serialized on one worker. Only its callback
// graphics context is used by SDK graphics threads; no VTK runs on a worker.
struct Session {
  struct Stream {
    QarAppVolumeId volume=qar_app_volume_id_default();
    bool volume_created{};
    QarRenderSender* sender{};
    uint64_t sent{};
    Clock::time_point retry_after{};
  };
  QarvtkHost& host;
  bool loaded{},initialized{};
  QarRuntime* runtime{};QarSession* session{};
  QarCancelToken* subscription{};
  std::vector<Stream> streams;
  qarvtk::LegacyPeerObserver peers;
  explicit Session(QarvtkHost& h):host(h){}
  ~Session(){
    // Panel video uses this session concurrently, but never outlives it.
    if(host.panels){host.panels->request_stop();host.panels->join();}
    if(subscription)qar_cancel_token_cancel(subscription);
    for(auto& stream:streams){
      if(stream.sender)qar_render_stream_handle_destroy(stream.sender);
      if(stream.volume_created)qar_app_volumes_close_volume(session,&stream.volume);
    }
    if(session)qar_session_destroy(session);
    if(runtime)qar_runtime_destroy(runtime);
    if(subscription)qar_cancel_token_handle_destroy(subscription);
    {std::lock_guard<std::mutex> lock(host.cancel_mutex);if(host.operation)qar_cancel_token_handle_destroy(host.operation);host.operation=nullptr;}
    if(initialized)qar_library_destroy();
    if(loaded)qar_library_unload();
  }
  void open(){
    const auto library=(std::filesystem::u8path(host.sdk_root)/"bin"/"qar-streaming-c.dll").u8string();
    if(!qar_library_load(library.c_str()))throw std::runtime_error("Cannot load matching QAROS session runtime");
    loaded=true;auto init=qar_library_init_default();init.enable_console_logging=false;init.log_folder_path=host.log_folder.c_str();
    checked(qar_library_init(&init),"initialize SDK");initialized=true;
    const auto folder=(std::filesystem::u8path(host.sdk_root)/"bin").u8string();
    auto ri=qar_runtime_init_default();ri.runtime_binaries_folder_path=folder.c_str();
    checked(qar_runtime_create(&ri,&runtime),"create SDK runtime");
    if(!runtime)throw std::runtime_error("SDK returned a null runtime");
    auto create=qar_session_create_init_default();create.header.next=&host.adapter.header;
    QarSessionInvite* raw{};checked(qar_runtime_create_session(runtime,&create,&raw),"create session");
    std::unique_ptr<QarSessionInvite,decltype(&qar_session_invite_handle_destroy)> invite(raw,qar_session_invite_handle_destroy);
    std::vector<uint8_t> bytes(1024*1024);size_t size{};
    checked(qar_session_invite_serialize(invite.get(),bytes.data(),bytes.size(),&size),"serialize local session");
    if(!size||size>bytes.size())throw std::runtime_error("Invalid session invite size");
    auto join=qar_session_join_init_default();join.header.next=&host.adapter.header;
    join.invite_data=bytes.data();join.invite_data_size=size;join.peer_spec_init.display_name="Slicer live renderer";
    checked(qar_session_join(&join,&session),"join session");
    if(!session)throw std::runtime_error("SDK returned a null session");
  }
  QarPeerId viewer(){
    checked(qar_cancel_token_create(&subscription),"create peer subscription");
    checked(qar_peer_subscribe_updates(session,on_peer,&peers,subscription),"subscribe peers");
    char connection[1024]{};
    if(host.target=="visualizer")checked(qar_session_invite_connection_string_visualizer(connection,sizeof(connection)),"visualizer address");
    else checked(qar_session_invite_connection_string_quest(connection,sizeof(connection)),"Quest address");
    auto init=qar_session_invite_peer_init_default();init.connection_string=connection;
    QarPeerId peer=qar_peer_id_default();host.deadline();host.set_status("Inviting "+host.target);
    checked(qar_session_invite_peer(session,&init,&peer,host.operation),"invite viewer");
    const auto end=Clock::now()+std::chrono::seconds(60);
    while(!host.stopping&&Clock::now()<end){
      if(const auto state=peers.state(peer)){
        if(*state==QAR_APP_STATE_SHUTTING_DOWN)throw std::runtime_error("Viewer is shutting down");
        host.set_status("Viewer observed; allowing receiver subscriptions to settle");
        if(!host.pause(std::chrono::seconds(2)))throw std::runtime_error("Live stream stopped");
        if(peers.state(peer)==QAR_APP_STATE_SHUTTING_DOWN)throw std::runtime_error("Viewer closed during startup");
        return peer;
      }
      host.pause(std::chrono::milliseconds(20));
    }
    throw std::runtime_error(host.stopping?"Live stream stopped":"No viewer peer update before timeout");
  }
  void start(const QarPeerId& peer){
    streams.resize(host.volumes.size());
    for(std::size_t i=0;i<streams.size()&&!host.stopping;++i)start_stream(peer,i);
    if(!host.stopping)host.panels->start(session,peer);
    host.set_status("Waiting for the viewer's first poses ("+std::to_string(streams.size())+" workspaces)");
    host.pause(std::chrono::milliseconds(1200));
  }
  void start_stream(const QarPeerId& peer,std::size_t index){
    auto& stream=streams[index];const auto& config=host.volumes[index];
    const QarPeerId* initial[]={&peer};auto app=qar_app_volume_init_default();
    app.display_name=config.name.c_str();
    qarvtk::apply_host_placement(app,config.placement);
    app.initial_peers=initial;app.initial_peer_count=1;
    checked(qar_app_volumes_add_volume(session,&app,&stream.volume),"create live app volume");stream.volume_created=true;
    {
      std::ostringstream line;line<<"Volume "<<index<<" ("<<config.name<<") workspace metres XYZ="<<app.size.width_meters<<','
        <<app.size.height_meters<<','<<app.size.length_meters<<"; room centre="
        <<app.pose.position.x<<','<<app.pose.position.y<<','<<app.pose.position.z;
      host.note(line.str());
    }
    auto gl=qar_stream_params_opengl_default();gl.context_type=QAR_OPENGL_CONTEXT_TYPE_WGL;
    gl.display_or_device_context=config.graphics->dc;gl.context=config.graphics->context;config.callbacks->configure(gl);
    auto init=qar_render_sender_init_default();init.graphics_api=QAR_GRAPHICS_API_OPENGL;init.header.next=&gl.header;
    init.peer_id=peer;init.app_volume_id=&stream.volume;init.enable_auto_reconnects=true;
    init.texture_layout=QAR_FRAME_LAYOUT_SEPARATED_TEXTURES;
    init.color_format=QAR_PIXEL_FORMAT_R8G8B8A8;init.depth_format=QAR_PIXEL_FORMAT_D32_FLOAT;init.frame_views_count=4;
    for(unsigned i=0;i<4;++i){init.frame_views[i]=qar_render_frame_view_default();
      init.frame_views[i].eye=i<2?QAR_VIDEO_FRAME_VIEW_EYE_LEFT:QAR_VIDEO_FRAME_VIEW_EYE_RIGHT;
      init.frame_views[i].data_type=i%2?QAR_VIDEO_FRAME_VIEW_TYPE_DEPTH:QAR_VIDEO_FRAME_VIEW_TYPE_COLOR;init.frame_views[i].texture_index=i;}
    host.deadline();host.set_status("Creating workspace "+std::to_string(index+1)+"/"+std::to_string(streams.size())+": "+config.name);
    checked(qar_render_sender_create(session,&init,host.operation,&stream.sender),"create live sender");
    if(!stream.sender)throw std::runtime_error("SDK returned a null sender");
    auto current=qar_video_frame_layout_default();
    checked(qar_render_sender_layout(stream.sender,&current),"read negotiated layout");
    const auto reduced=qarvtk::half_depth_layout(current);
    checked(qar_render_sender_change_layout(stream.sender,&reduced),"set half-resolution depth layout");
    host.note("App placement uses SDK app_pose/app_scale; depth requested at half color width and height");
  }
};
}

void QarvtkHost::run() noexcept {
  try {
    Session sdk(*this);sdk.open();if(!stopping){const auto peer=sdk.viewer();if(!stopping)sdk.start(peer);}
    auto last=Clock::now(),cycle_start=last,window_start=last;
    FrameTimings totals;
    double wait_ms=0,metadata_ms=0,gui_ms=0,show_ms=0;
    uint64_t measured=0;
    qarvtk::HostStreamScheduler scheduler;
    auto report=[&](bool force){
      const double elapsed=milliseconds(window_start);
      if(!measured||(!force&&elapsed<5000))return;
      const double count=static_cast<double>(measured);
      std::ostringstream line;line<<std::fixed<<std::setprecision(2)
        <<"PERF_NATIVE frames="<<measured<<" submitted_fps="<<count*1000/elapsed
        <<" eye_size="<<request.eyes[0].width<<'x'<<request.eyes[0].height
        <<" depth_size="<<request.eyes[0].depth_width<<'x'<<request.eyes[0].depth_height
        <<" sdk_wait_ms="<<wait_ms/count<<" metadata_ms="<<metadata_ms/count
        <<" gui_wait_ms="<<gui_ms/count<<" sdk_show_ms="<<show_ms/count
        <<" host_sync_ms="<<totals.host_sync/count<<" composite_cpu_ms="<<totals.composite/count
        <<" copy_cpu_ms="<<totals.copy/count<<" copy_finish_ms="<<totals.copy_finish/count
        <<" volume_frames=";
      for(std::size_t i=0;i<sdk.streams.size();++i)line<<(i?",":"")<<i<<':'<<sdk.streams[i].sent;
      note(line.str());totals={};wait_ms=metadata_ms=gui_ms=show_ms=0;measured=0;window_start=Clock::now();
    };
    while(!stopping){
      if(Clock::now()-last>std::chrono::seconds(60))throw std::runtime_error("No viewer frame/pose for 60 seconds");
      std::unique_ptr<QarRenderFrameInfo,decltype(&qar_render_frame_info_handle_destroy)> info(nullptr,qar_render_frame_info_handle_destroy);
      const auto selected=scheduler.select(sdk.streams.size(),[&](std::size_t index){
        auto& stream=sdk.streams[index];
        if(stopping||Clock::now()<stream.retry_after)return false;
        QarRenderFrameInfo* raw{};bool ready=false;
        const auto result=qar_render_sender_try_begin_frame(stream.sender,&raw,&ready);
        info.reset(raw);
        if(qarvtk::legacy_begin_frame_wait(result,stream.sent==0)!=qarvtk::LegacyFrameWait::none){
          stream.retry_after=Clock::now()+std::chrono::milliseconds(100);info.reset();return false;
        }
        if(qar_result_has_code(result,QAR_STATUS_MEDIA_STREAMING_STREAM_IS_RECONNECTING)||
           qar_result_has_code(result,QAR_STATUS_MEDIA_STREAMING_NO_ACTIVE_TRANSFERS)){
          stream.retry_after=Clock::now()+std::chrono::milliseconds(2);info.reset();return false;
        }
        checked(result,"begin live frame");
        if(!ready){info.reset();return false;}
        if(!info)throw std::runtime_error("Ready frame has no metadata");
        return true;
      });
      if(!selected){pause(std::chrono::milliseconds(2));continue;}
      auto& stream=sdk.streams[*selected];
      const auto& placement=volumes[*selected].placement;
      const auto ready_at=Clock::now();
      auto access=qar_video_frame_opengl_default();checked(qar_render_sender_frame_opengl(stream.sender,&access),"access frame textures");
      auto next=layout(access);const auto next_views=qarvtk::validate_stereo(next);
      QarvtkHostFrame next_request{};next_request.serial=sent+1;
      next_request.volume_index=static_cast<uint32_t>(*selected);
      next_request.near_plane=static_cast<float>(.05/placement.app_scale);
      next_request.far_plane=static_cast<float>(20./placement.app_scale);
      for(unsigned i=0;i<2;++i){
        const auto& view=next.views[next_views[i].color];auto& eye=next_request.eyes[i];
        QarPose pose=qar_pose_default();QarFov fov=qar_fov_default();
        checked(qar_render_frame_info_get_view_pose(info.get(),next_views[i].color,&pose),"eye pose");
        checked(qar_render_frame_info_get_view_fov(info.get(),next_views[i].color,&fov),"eye FOV");
        eye.position[0]=pose.position.x;eye.position[1]=pose.position.y;eye.position[2]=pose.position.z;
        eye.orientation[0]=pose.orientation.x;eye.orientation[1]=pose.orientation.y;eye.orientation[2]=pose.orientation.z;eye.orientation[3]=pose.orientation.w;
        eye.fov[0]=fov.angle_left;eye.fov[1]=fov.angle_right;eye.fov[2]=fov.angle_up;eye.fov[3]=fov.angle_down;
        eye.width=qarvtk::width(view);eye.height=qarvtk::height(view);
        const auto& depth=next.views[next_views[i].depth];
        eye.depth_width=qarvtk::width(depth);eye.depth_height=qarvtk::height(depth);
        if(eye.depth_width!=(eye.width+1)/2||eye.depth_height!=(eye.height+1)/2)
          throw std::runtime_error("SDK did not retain the requested half-resolution depth layout");
      }
      const auto posted_at=Clock::now();
      FrameTimings copied;
      {
        std::unique_lock<std::mutex> lock(mutex);
        frame=std::move(next);views=next_views;request=next_request;timings={};lease.post(request.serial);
        condition.wait(lock,[&]{return lease.submitted()||(stopping&&!lease.acquired());});
        if(stopping)break;
        copied=timings;lease.consume();
      }
      const auto show_at=Clock::now();
      auto show=qar_render_frame_show_default();
      show.rendered_near_far={static_cast<float>(request.near_plane),static_cast<float>(request.far_plane)};show.depth_scale=1;
      checked(qar_render_sender_show_frame(stream.sender,&show),"submit live stereo frame");
      ++sent;++stream.sent;last=Clock::now();
      totals+=copied;++measured;wait_ms+=milliseconds(cycle_start,ready_at);
      metadata_ms+=milliseconds(ready_at,posted_at);gui_ms+=milliseconds(posted_at,show_at);
      show_ms+=milliseconds(show_at,last);cycle_start=last;report(false);
      if(sent==1||sent%120==0)set_status("Live host renderer: "+std::to_string(volumes.size())+
          " workspaces; submitted "+std::to_string(sent)+" stereo frames total");
    }
    report(true);
  } catch(const std::exception& e){if(!stopping)fail(e.what());}
    catch(...){if(!stopping)fail("Unknown native host transport failure");}
  // Session destruction (and all SDK workers) must finish before destroy is allowed.
  note("SDK worker exited; submitted total="+std::to_string(sent));
  done=true;condition.notify_all();
}

extern "C" {
const char* qarvtk_host_info(){
  return "{\"host_abi\":5,\"modern_api\":0,\"header_sha256\":\"" QARVTK_HOST_SDK_HASH "\",\"eye_size\":104,\"frame_size\":240,\"placement_size\":112,\"volume_size\":120}";
}
int qarvtk_host_create(const char* sdk,const char* target,const char* folder,const QarvtkHostPlacement* placement,
                      QarvtkHost** result,char* error,uint32_t size){
  QarvtkHostVolume volume{};if(placement)volume.placement=*placement;volume.name="Slicer live renderer";
  return qarvtk_host_create_volumes(sdk,target,folder,placement?&volume:nullptr,1,result,error,size);
}
int qarvtk_host_create_volumes(const char* sdk,const char* target,const char* folder,
    const QarvtkHostVolume* volumes,uint32_t count,QarvtkHost** result,char* error,uint32_t size){
  if(result)*result=nullptr;
  bool expected=false;
  if(!active.compare_exchange_strong(expected,true)){message(error,size,"Only one live host transport may run in this Slicer process");return -1;}
  try {
    if(!sdk||!target||!folder||!volumes||!count||count>32||!result)throw std::invalid_argument("Expected 1 to 32 host workspaces");
    auto host=std::make_unique<QarvtkHost>();host->sdk_root=sdk;host->target=target;host->log_folder=folder;
    for(uint32_t i=0;i<count;++i){
      auto probe=qar_app_volume_init_default();qarvtk::apply_host_placement(probe,volumes[i].placement);
      QarvtkHost::Volume volume;volume.placement=volumes[i].placement;
      volume.name=volumes[i].name&&*volumes[i].name?volumes[i].name:"Slicer volume "+std::to_string(i+1);
      host->volumes.push_back(std::move(volume));
    }
    host->initialize();
    *result=host.release();return 0;
  } catch(const std::exception& e){message(error,size,e.what());active=false;return -1;}
    catch(...){message(error,size,"Cannot initialize host transport");active=false;return -1;}
}
int qarvtk_host_poll(QarvtkHost* h,QarvtkHostFrame* out){
  if(!h||!out)return -1;
  try {
    h->gui();std::lock_guard<std::mutex> lock(h->mutex);
    if(h->failed)return -1;if(h->done)return 2;
    if(h->stopping||!h->lease.acquire())return 0;
    *out=h->request;return 1;
  } catch(const std::exception& e){h->fail(e.what());return -1;}
}
int qarvtk_host_color(QarvtkHost* h,uint64_t serial,uint32_t eye,uint32_t color,uint32_t depth,uint32_t width,uint32_t height){
  if(!h)return -1;try{h->copy(serial,eye,{color,depth,width,height},false);return 0;}
  catch(const std::exception& e){h->fail(e.what());return -1;}
}
int qarvtk_host_depth(QarvtkHost* h,uint64_t serial,uint32_t eye,uint32_t color,uint32_t depth,uint32_t vc,uint32_t vd,uint32_t width,uint32_t height){
  if(!h)return -1;try{h->copy(serial,eye,{color,depth,width,height},true,vc,vd);return 0;}
  catch(const std::exception& e){h->fail(e.what());return -1;}
}
int qarvtk_host_finish(QarvtkHost* h,uint64_t serial){
  if(!h)return -1;
  try {
    h->gui();std::lock_guard<std::mutex> lock(h->mutex);
    if(h->stopping)throw std::runtime_error("Incomplete host stereo frame");
    h->lease.finish(serial);h->condition.notify_all();return 0;
  } catch(const std::exception& e){h->fail(e.what());return -1;}
}
void qarvtk_host_stop(QarvtkHost* h){if(h)try{h->stop();}catch(const std::exception& e){h->fail(e.what());}}
int qarvtk_host_destroy(QarvtkHost* h){
  if(!h)return 1;
  if(GetCurrentThreadId()!=h->owner||!h->done)return 0;
  delete h;active=false;return 1;
}
void qarvtk_host_status(QarvtkHost* h,char* text,uint32_t size){
  if(!h){message(text,size,"Stopped");return;}
  std::lock_guard<std::mutex> lock(h->mutex);message(text,size,h->status);
}
int qarvtk_host_panel_create(QarvtkHost* h,const char* name,uint32_t w,uint32_t height,
    double x,double y,double z,double width_meters,QarvtkHostPanel** out,char* error,uint32_t size){
  if(out)*out=nullptr;
  try{
    if(!h||!out||!h->panels||h->stopping)throw std::invalid_argument("No active panel transport");
    *out=reinterpret_cast<QarvtkHostPanel*>(h->panels->create(name,w,height,x,y,z,width_meters));return 0;
  }catch(const std::exception& e){message(error,size,e.what());return -1;}
}
int qarvtk_host_panel_capture(QarvtkHost* h,QarvtkHostPanel* p,uint32_t color,uint32_t w,uint32_t height,char* error,uint32_t size){
  try{
    if(!h||!h->panels)throw std::invalid_argument("No active panel transport");
    if(h->stopping)return 0;
    return h->panels->capture(reinterpret_cast<qarvtk::HostPanel*>(p),color,w,height);
  }catch(const std::exception& e){message(error,size,e.what());return -1;}
}
int qarvtk_host_panel_visible(QarvtkHost* h,QarvtkHostPanel* p,uint32_t visible){
  try{if(!h||!h->panels)return -1;h->panels->visible(reinterpret_cast<qarvtk::HostPanel*>(p),visible!=0);return 0;}
  catch(...){return -1;}
}
void qarvtk_host_panel_close(QarvtkHost* h,QarvtkHostPanel* p){
  if(h&&h->panels)try{h->panels->close(reinterpret_cast<qarvtk::HostPanel*>(p));}catch(...){}
}
void qarvtk_host_panel_status(QarvtkHost* h,QarvtkHostPanel* p,char* text,uint32_t size){
  try{message(text,size,h&&h->panels?h->panels->status(reinterpret_cast<qarvtk::HostPanel*>(p)):"Stopped");}
  catch(const std::exception& e){message(text,size,e.what());}
}
}
static_assert(sizeof(QarvtkHostEye)==104&&sizeof(QarvtkHostFrame)==240&&sizeof(QarvtkHostPlacement)==112&&sizeof(QarvtkHostVolume)==120,"Unexpected host C ABI packing");
