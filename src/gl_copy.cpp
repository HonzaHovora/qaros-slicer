#include "qarvtk/gl.hpp"
#include "qarvtk/gl_copy.hpp"
#include <algorithm>
#include <array>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
namespace qarvtk { namespace {
const char* vertex=R"(#version 330 core
out vec2 uv;
void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);uv=p;gl_Position=vec4(p*2.0-1.0,0,1);}
)";
const char* fragment=R"(#version 330 core
in vec2 uv;out vec4 pixel;uniform sampler2D sourceImage;uniform ivec2 flipAxis;uniform int isDepth;
void main(){vec2 t=mix(uv,1.0-uv,vec2(flipAxis));vec4 v=texture(sourceImage,t);
if(isDepth!=0){pixel=vec4(v.r,0,0,1);gl_FragDepth=v.r;}else{pixel=v;}}
)";
unsigned compile(GLenum kind,const char* text){
  const auto shader=glCreateShader(kind);glShaderSource(shader,1,&text,nullptr);glCompileShader(shader);
  GLint ok=0;glGetShaderiv(shader,GL_COMPILE_STATUS,&ok);
  if(!ok){char log[2048]{};glGetShaderInfoLog(shader,2048,nullptr,log);glDeleteShader(shader);throw std::runtime_error(log);}return shader;
}
struct State {
  GLint read{},draw{},program{},vao{},active{},texture{},arrayTexture{},sampler{},viewport[4]{},depthfunc{};
  GLboolean depthmask{},colormask[4]{};
  const std::array<GLenum,6> caps{GL_DEPTH_TEST,GL_BLEND,GL_SCISSOR_TEST,GL_CULL_FACE,GL_FRAMEBUFFER_SRGB,GL_RASTERIZER_DISCARD};
  std::array<GLboolean,6> enabled{};
  State(){
    glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING,&read);glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING,&draw);
    glGetIntegerv(GL_CURRENT_PROGRAM,&program);glGetIntegerv(GL_VERTEX_ARRAY_BINDING,&vao);
    glGetIntegerv(GL_ACTIVE_TEXTURE,&active);glActiveTexture(GL_TEXTURE0);
    glGetIntegerv(GL_TEXTURE_BINDING_2D,&texture);glGetIntegerv(GL_SAMPLER_BINDING,&sampler);
    glGetIntegerv(GL_TEXTURE_BINDING_2D_ARRAY,&arrayTexture);
    glGetIntegerv(GL_VIEWPORT,viewport);glGetBooleanv(GL_DEPTH_WRITEMASK,&depthmask);
    glGetBooleanv(GL_COLOR_WRITEMASK,colormask);glGetIntegerv(GL_DEPTH_FUNC,&depthfunc);
    for(std::size_t i=0;i<caps.size();++i)enabled[i]=glIsEnabled(caps[i]);
  }
  ~State(){
    glBindFramebuffer(GL_READ_FRAMEBUFFER,read);glBindFramebuffer(GL_DRAW_FRAMEBUFFER,draw);
    glUseProgram(program);glBindVertexArray(vao);glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D,texture);glBindTexture(GL_TEXTURE_2D_ARRAY,arrayTexture);
    glBindSampler(0,sampler);glActiveTexture(active);
    glViewport(viewport[0],viewport[1],viewport[2],viewport[3]);glDepthMask(depthmask);glDepthFunc(depthfunc);
    glColorMask(colormask[0],colormask[1],colormask[2],colormask[3]);
    for(std::size_t i=0;i<caps.size();++i)if(enabled[i])glEnable(caps[i]);else glDisable(caps[i]);
  }
};
std::string hex(GLenum value){std::ostringstream out;out<<"0x"<<std::hex<<value;return out.str();}
const char* framebuffer_status(GLenum status){
  switch(status){
    case GL_FRAMEBUFFER_COMPLETE:return "GL_FRAMEBUFFER_COMPLETE";
    case GL_FRAMEBUFFER_UNDEFINED:return "GL_FRAMEBUFFER_UNDEFINED";
    case GL_FRAMEBUFFER_INCOMPLETE_ATTACHMENT:return "GL_FRAMEBUFFER_INCOMPLETE_ATTACHMENT";
    case GL_FRAMEBUFFER_INCOMPLETE_MISSING_ATTACHMENT:return "GL_FRAMEBUFFER_INCOMPLETE_MISSING_ATTACHMENT";
    case GL_FRAMEBUFFER_INCOMPLETE_DRAW_BUFFER:return "GL_FRAMEBUFFER_INCOMPLETE_DRAW_BUFFER";
    case GL_FRAMEBUFFER_INCOMPLETE_READ_BUFFER:return "GL_FRAMEBUFFER_INCOMPLETE_READ_BUFFER";
    case GL_FRAMEBUFFER_UNSUPPORTED:return "GL_FRAMEBUFFER_UNSUPPORTED";
    case GL_FRAMEBUFFER_INCOMPLETE_MULTISAMPLE:return "GL_FRAMEBUFFER_INCOMPLETE_MULTISAMPLE";
    case GL_FRAMEBUFFER_INCOMPLETE_LAYER_TARGETS:return "GL_FRAMEBUFFER_INCOMPLETE_LAYER_TARGETS";
    default:return "unknown framebuffer status";
  }
}
void checked_gl(const std::string& stage){
  const auto error=glGetError();
  if(error!=GL_NO_ERROR)throw std::runtime_error(stage+"; GL error="+hex(error));
}
// The C SDK exposes an object name and layer count, but no GL target. A
// single-layer texture can still be a GL_TEXTURE_2D_ARRAY. In GL 3.3 a bind to
// the wrong target is rejected without modifying the texture or its binding.
GLenum bind_destination(unsigned name,const std::string& description){
  glBindTexture(GL_TEXTURE_2D,name);
  const auto error=glGetError();
  if(error==GL_NO_ERROR)return GL_TEXTURE_2D;
  if(error!=GL_INVALID_OPERATION)
    throw std::runtime_error("Bind destination failed: "+description+"; GL error="+hex(error));
  glBindTexture(GL_TEXTURE_2D_ARRAY,name);
  checked_gl("Destination is neither a shared 2D texture nor a 2D array: "+description);
  return GL_TEXTURE_2D_ARRAY;
}
struct Attachment {
  ~Attachment(){
    // Also detach on a failed completeness check; do not retain SDK textures.
    glFramebufferTexture(GL_DRAW_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,0,0);
    glFramebufferTexture(GL_DRAW_FRAMEBUFFER,GL_DEPTH_ATTACHMENT,0,0);
  }
};
}
GlCopy::GlCopy(){
  auto v=compile(GL_VERTEX_SHADER,vertex),f=compile(GL_FRAGMENT_SHADER,fragment);
  program_=glCreateProgram();glAttachShader(program_,v);glAttachShader(program_,f);glLinkProgram(program_);
  glDeleteShader(v);glDeleteShader(f);GLint ok=0;glGetProgramiv(program_,GL_LINK_STATUS,&ok);
  if(!ok){glDeleteProgram(program_);program_=0;throw std::runtime_error("Cannot link GPU copy shader");}
  glGenVertexArrays(1,&vao_);glGenFramebuffers(1,&fbo_);
}
GlCopy::~GlCopy(){glDeleteFramebuffers(1,&fbo_);glDeleteVertexArrays(1,&vao_);glDeleteProgram(program_);}
void GlCopy::plane(unsigned source,const Texture& t,const View& v,bool depth,bool report){
  std::ostringstream context;
  context<<(v.eye==Eye::left?"left":"right")<<' '<<(depth?"depth":"color")
    <<"; texture["<<v.texture<<"]="<<t.handle<<"; source="<<source
    <<"; SDK size="<<t.width<<'x'<<t.height<<"; layers="<<t.layers<<"; layer="<<v.layer;
  if(t.layers!=1||v.layer!=0||!glIsTexture(t.handle)||source==t.handle)
    throw std::runtime_error("Destination is not a shared single-layer texture, or aliases the source: "+context.str());
  const auto target=bind_destination(t.handle,context.str());
  GLint internal=0,w=0,h=0,layers=1,base=0,max=0;
  glGetTexLevelParameteriv(target,0,GL_TEXTURE_INTERNAL_FORMAT,&internal);
  glGetTexLevelParameteriv(target,0,GL_TEXTURE_WIDTH,&w);glGetTexLevelParameteriv(target,0,GL_TEXTURE_HEIGHT,&h);
  if(target==GL_TEXTURE_2D_ARRAY)glGetTexLevelParameteriv(target,0,GL_TEXTURE_DEPTH,&layers);
  glGetTexParameteriv(target,GL_TEXTURE_BASE_LEVEL,&base);glGetTexParameteriv(target,GL_TEXTURE_MAX_LEVEL,&max);
  checked_gl("Query destination: "+context.str());
  context<<"; target="<<(target==GL_TEXTURE_2D?"GL_TEXTURE_2D":"GL_TEXTURE_2D_ARRAY")
    <<"; format="<<hex(internal)<<"; GL size="<<w<<'x'<<h<<'x'<<layers<<"; mip range="<<base<<".."<<max
    <<"; view=("<<v.x0<<','<<v.y0<<")->("<<v.x1<<','<<v.y1<<")"
    <<"; source origin=bottom-left; stream origin=top-left";
  if(report)std::cout<<"GPU copy destination: "<<context.str()<<'\n';
  if(w!=static_cast<int>(t.width)||h!=static_cast<int>(t.height)||layers!=static_cast<int>(t.layers))
    throw std::runtime_error("SDK texture dimensions disagree with OpenGL: "+context.str());
  const bool nativeDepth=internal==GL_DEPTH_COMPONENT32F||internal==GL_DEPTH_COMPONENT24||internal==GL_DEPTH_COMPONENT16;
  if((depth&&!nativeDepth&&internal!=GL_R32F)||(!depth&&internal!=GL_RGBA8&&internal!=GL_SRGB8_ALPHA8))
    throw std::runtime_error("Unsupported SDK texture internal format: "+context.str());
  glBindFramebuffer(GL_FRAMEBUFFER,fbo_);
  checked_gl("Bind copy framebuffer: "+context.str());
  Attachment attached;
  glFramebufferTexture(GL_DRAW_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,0,0);
  glFramebufferTexture(GL_DRAW_FRAMEBUFFER,GL_DEPTH_ATTACHMENT,0,0);
  const auto attachment=nativeDepth?GL_DEPTH_ATTACHMENT:GL_COLOR_ATTACHMENT0;
  if(target==GL_TEXTURE_2D_ARRAY)
    glFramebufferTextureLayer(GL_DRAW_FRAMEBUFFER,attachment,t.handle,0,static_cast<GLint>(v.layer));
  else glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER,attachment,target,t.handle,0);
  glDrawBuffer(nativeDepth?GL_NONE:GL_COLOR_ATTACHMENT0);
  glReadBuffer(nativeDepth?GL_NONE:GL_COLOR_ATTACHMENT0);
  const auto status=glCheckFramebufferStatus(GL_DRAW_FRAMEBUFFER),error=glGetError();
  if(error!=GL_NO_ERROR||status!=GL_FRAMEBUFFER_COMPLETE)
    throw std::runtime_error("Destination framebuffer is incomplete: "+std::string(framebuffer_status(status))
      +" ("+hex(status)+"); GL error="+hex(error)+"; "+context.str());
  if(nativeDepth){glEnable(GL_DEPTH_TEST);glDepthFunc(GL_ALWAYS);glDepthMask(GL_TRUE);}else{glDisable(GL_DEPTH_TEST);glDepthMask(GL_FALSE);}
  glViewport(std::min(v.x0,v.x1),std::min(v.y0,v.y1),width(v),height(v));
  glBindTexture(GL_TEXTURE_2D,source);
  // VTK's framebuffer has row zero at the bottom. QAROS view pixels run
  // top-to-bottom (as in its CPU/D3D/Vulkan renderers). Convert that origin
  // for BOTH color and depth, then compose with each view's optional flips.
  glUniform2i(glGetUniformLocation(program_,"flipAxis"),v.x1<v.x0,v.y1>v.y0);
  glUniform1i(glGetUniformLocation(program_,"isDepth"),depth?1:0);
  glDrawArrays(GL_TRIANGLES,0,3);
  checked_gl("Draw GPU copy: "+context.str());
}
void GlCopy::copy(const RenderedEye& s,const Frame& f,const EyeViews& v,bool report){
  (void)validate_stereo(f);
  if(v.color>=f.views.size()||v.depth>=f.views.size())throw std::invalid_argument("Missing copy view");
  checked_gl("Before GPU copy (render/SDK context)");
  State state;
  for(auto cap:state.caps)glDisable(cap);
  glColorMask(GL_TRUE,GL_TRUE,GL_TRUE,GL_TRUE);glUseProgram(program_);glBindVertexArray(vao_);
  glActiveTexture(GL_TEXTURE0);glBindSampler(0,0);glUniform1i(glGetUniformLocation(program_,"sourceImage"),0);
  checked_gl("Prepare GPU copy state");
  const auto& c=f.views[v.color];const auto& d=f.views[v.depth];
  plane(s.color,f.textures[c.texture],c,false,report);plane(s.depth,f.textures[d.texture],d,true,report);
  const auto error=glGetError();if(error!=GL_NO_ERROR)throw std::runtime_error("OpenGL copy error: "+std::to_string(error));
}
void GlCopy::finish(){glFinish();}
}
