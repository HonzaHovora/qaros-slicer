#include "qarvtk/gl.hpp"
#include "qarvtk/renderer.hpp"
#include <vtkActor.h>
#include <vtkCallbackCommand.h>
#include <vtkCamera.h>
#include <vtkCommand.h>
#include <vtkCubeSource.h>
#include <vtkGenericOpenGLRenderWindow.h>
#include <vtkMatrix4x4.h>
#include <vtkNew.h>
#include <vtkSmartPointer.h>
#include <vtkOpenGLFramebufferObject.h>
#include <vtkPolyData.h>
#include <vtkPolyDataMapper.h>
#include <vtkProperty.h>
#include <vtkRenderer.h>
#include <vtkTextureObject.h>
#include <vtkTransform.h>
#include <vtkTransformPolyDataFilter.h>
#include <vtkVersion.h>
#include <vtkXMLPolyDataReader.h>
#include <cmath>
#include <iostream>
#include <sstream>
#include <stdexcept>

namespace qarvtk {
struct Renderer::Impl {
  GLFWwindow* main{}; GLFWwindow* sdk{}; bool glfw_started{};
  vtkSmartPointer<vtkGenericOpenGLRenderWindow> window;
  vtkSmartPointer<vtkRenderer> renderer;
  vtkSmartPointer<vtkPolyDataMapper> mapper;
  vtkSmartPointer<vtkActor> actor;
  ~Impl() {
    if(main) glfwMakeContextCurrent(main);
    if(window) { window->Finalize(); window=nullptr; }
    actor=nullptr; mapper=nullptr; renderer=nullptr;
    if(sdk) glfwDestroyWindow(sdk);
    if(main) glfwDestroyWindow(main);
    if(glfw_started) glfwTerminate();
  }
};
Renderer::Renderer(bool visible):impl_(std::make_unique<Impl>()) {
  glfwSetErrorCallback([](int code,const char* message){std::cerr<<"GLFW "<<code<<": "<<message<<'\n';});
  if(!glfwInit()) throw std::runtime_error("Cannot initialize GLFW. Linux requires an X11 display (use xvfb-run for tests).");
  impl_->glfw_started=true;
  glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR,3);glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR,3);
  glfwWindowHint(GLFW_OPENGL_PROFILE,GLFW_OPENGL_CORE_PROFILE);
  glfwWindowHint(GLFW_VISIBLE,visible?GLFW_TRUE:GLFW_FALSE);
  impl_->main=glfwCreateWindow(640,640,"QAROS VTK preview",nullptr,nullptr);
  if(!impl_->main) throw std::runtime_error("Cannot create OpenGL 3.3 render context");
  glfwWindowHint(GLFW_VISIBLE,GLFW_FALSE);
  impl_->sdk=glfwCreateWindow(32,32,"QAROS shared context",nullptr,impl_->main);
  if(!impl_->sdk) throw std::runtime_error("Cannot create shared SDK context");
  make_current();glfwSwapInterval(0);
  auto& w=impl_->window;w=vtkSmartPointer<vtkGenericOpenGLRenderWindow>::New();
  w->SetOwnContext(0);w->SetMultiSamples(0);w->SetSize(640,640);
  w->SetFrameBlitMode(vtkOpenGLRenderWindow::NoBlit);
  w->SetReadyForRendering(true);
  vtkNew<vtkCallbackCommand> observer;
  observer->SetClientData(impl_.get());
  observer->SetCallback([](vtkObject*,unsigned long event,void* data,void* call){
    auto* p=static_cast<Impl*>(data);
    if(event==vtkCommand::WindowMakeCurrentEvent) glfwMakeContextCurrent(p->main);
    else if(event==vtkCommand::WindowIsCurrentEvent) *static_cast<bool*>(call)=glfwGetCurrentContext()==p->main;
    else if(event==vtkCommand::WindowSupportsOpenGLEvent) *static_cast<int*>(call)=1;
    else if(event==vtkCommand::WindowIsDirectEvent) *static_cast<int*>(call)=1;
  });
  for(auto e:{vtkCommand::WindowMakeCurrentEvent,vtkCommand::WindowIsCurrentEvent,
              vtkCommand::WindowSupportsOpenGLEvent,vtkCommand::WindowIsDirectEvent}) w->AddObserver(e,observer);
  impl_->renderer=vtkSmartPointer<vtkRenderer>::New();
  impl_->renderer->SetBackground(0,0,0);impl_->renderer->SetBackgroundAlpha(0);
  w->AddRenderer(impl_->renderer);
  impl_->mapper=vtkSmartPointer<vtkPolyDataMapper>::New();
  impl_->mapper->ScalarVisibilityOff();
  impl_->actor=vtkSmartPointer<vtkActor>::New();impl_->actor->SetMapper(impl_->mapper);
  impl_->actor->GetProperty()->SetColor(.15,.8,.35);
  impl_->actor->GetProperty()->LightingOff();
  impl_->renderer->AddActor(impl_->actor);
  vtkNew<vtkCubeSource> cube;cube->SetCenter(0,0,0);cube->SetXLength(.4);cube->SetYLength(.4);cube->SetZLength(.4);cube->Update();
  impl_->mapper->SetInputData(cube->GetOutput());
  Pose initial; initial.position.z=2;
  render(initial, {}, {}, 640,640); // Initialize VTK's GL loader and render targets.
}
Renderer::~Renderer()=default;
void Renderer::make_current(){glfwMakeContextCurrent(impl_->main);}
GLFWwindow* Renderer::main_window()const{return impl_->main;}
GLFWwindow* Renderer::sdk_window()const{return impl_->sdk;}
void Renderer::poll(){glfwPollEvents();}
bool Renderer::closing()const{return glfwWindowShouldClose(impl_->main)!=0;}
void Renderer::set_polydata(vtkPolyData* data,double scale,bool ras){
  if(!data||data->GetNumberOfPoints()==0)throw std::invalid_argument("Scene is empty");
  if(!std::isfinite(scale)||scale<=0)throw std::invalid_argument("meters-per-unit must be positive and finite");
  vtkNew<vtkMatrix4x4> m;m->Zero();m->SetElement(3,3,1);
  m->SetElement(0,0,scale);
  if(ras){m->SetElement(1,2,scale);m->SetElement(2,1,-scale);}
  else{m->SetElement(1,1,scale);m->SetElement(2,2,scale);}
  vtkNew<vtkTransform> t;t->SetMatrix(m);
  vtkNew<vtkTransformPolyDataFilter> filter;filter->SetTransform(t);filter->SetInputData(data);filter->Update();
  // Deep-copy a complete scene before swapping it into the active mapper.
  vtkNew<vtkPolyData> copy;copy->DeepCopy(filter->GetOutput());
  impl_->mapper->SetInputData(copy);
}
void Renderer::load_vtp(const std::string& path,double scale,bool ras){
  vtkNew<vtkXMLPolyDataReader> reader;
  if(!reader->CanReadFile(path.c_str()))throw std::runtime_error("Cannot read VTP scene: "+path);
  reader->SetFileName(path.c_str());reader->Update();set_polydata(reader->GetOutput(),scale,ras);
}
RenderedEye Renderer::render(Pose pose,Fov fov,Clip clip,unsigned width,unsigned height){
  validate(pose);const auto matrix=projection(fov,clip);
  if(!width||!height||width>16384||height>16384)throw std::invalid_argument("Invalid render dimensions");
  make_current();
  auto* c=impl_->renderer->GetActiveCamera();
  const auto forward=rotate(pose.orientation,{0,0,-1}),up=rotate(pose.orientation,{0,1,0});
  c->SetPosition(pose.position.x,pose.position.y,pose.position.z);
  c->SetFocalPoint(pose.position.x+forward.x,pose.position.y+forward.y,pose.position.z+forward.z);
  c->SetViewUp(up.x,up.y,up.z);c->SetClippingRange(clip.near_plane,clip.far_plane);
  vtkNew<vtkMatrix4x4> p;for(int i=0;i<4;++i)for(int j=0;j<4;++j)p->SetElement(i,j,matrix[i*4+j]);
  c->SetExplicitProjectionTransformMatrix(p);c->SetUseExplicitProjectionTransformMatrix(true);
  impl_->window->SetSize(static_cast<int>(width),static_cast<int>(height));impl_->window->Render();
  auto* fbo=impl_->window->GetRenderFramebuffer();
  auto* color=fbo?fbo->GetColorAttachmentAsTextureObject(0):nullptr;
  auto* depth=fbo?fbo->GetDepthAttachmentAsTextureObject():nullptr;
  if(!color||!depth)throw std::runtime_error("VTK did not expose color/depth textures; MSAA must be disabled");
  return {color->GetHandle(),depth->GetHandle(),width,height};
}
void Renderer::present(){
  make_current();GLint previousRead=0,previousDraw=0;
  glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING,&previousRead);glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING,&previousDraw);
  auto* fbo=impl_->window->GetRenderFramebuffer();const auto* size=impl_->window->GetSize();
  int w=0,h=0;glfwGetFramebufferSize(impl_->main,&w,&h);
  glBindFramebuffer(GL_READ_FRAMEBUFFER,fbo->GetFBOIndex());glReadBuffer(GL_COLOR_ATTACHMENT0);
  glBindFramebuffer(GL_DRAW_FRAMEBUFFER,0);
  glBlitFramebuffer(0,0,size[0],size[1],0,0,w,h,GL_COLOR_BUFFER_BIT,GL_NEAREST);
  glBindFramebuffer(GL_READ_FRAMEBUFFER,previousRead);glBindFramebuffer(GL_DRAW_FRAMEBUFFER,previousDraw);
  glfwSwapBuffers(impl_->main);
}
std::string Renderer::capabilities()const{
  std::ostringstream o;o<<"VTK "<<vtkVersion::GetVTKVersion()<<"; GL "<<glGetString(GL_VERSION)
    <<"; vendor "<<glGetString(GL_VENDOR)<<"; renderer "<<glGetString(GL_RENDERER);return o.str();
}
}
