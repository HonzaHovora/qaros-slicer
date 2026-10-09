#include "qarvtk/gl.hpp"
#include "qarvtk/gl_copy.hpp"
#include <algorithm>
#include <array>
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
  GLint read{},draw{},program{},vao{},active{},texture{},sampler{},viewport[4]{},depthfunc{};
  GLboolean depthmask{},colormask[4]{};
  const std::array<GLenum,6> caps{GL_DEPTH_TEST,GL_BLEND,GL_SCISSOR_TEST,GL_CULL_FACE,GL_FRAMEBUFFER_SRGB,GL_RASTERIZER_DISCARD};
  std::array<GLboolean,6> enabled{};
  State(){
    glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING,&read);glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING,&draw);
    glGetIntegerv(GL_CURRENT_PROGRAM,&program);glGetIntegerv(GL_VERTEX_ARRAY_BINDING,&vao);
    glGetIntegerv(GL_ACTIVE_TEXTURE,&active);glActiveTexture(GL_TEXTURE0);
    glGetIntegerv(GL_TEXTURE_BINDING_2D,&texture);glGetIntegerv(GL_SAMPLER_BINDING,&sampler);
    glGetIntegerv(GL_VIEWPORT,viewport);glGetBooleanv(GL_DEPTH_WRITEMASK,&depthmask);
    glGetBooleanv(GL_COLOR_WRITEMASK,colormask);glGetIntegerv(GL_DEPTH_FUNC,&depthfunc);
    for(std::size_t i=0;i<caps.size();++i)enabled[i]=glIsEnabled(caps[i]);
  }
  ~State(){
    glBindFramebuffer(GL_READ_FRAMEBUFFER,read);glBindFramebuffer(GL_DRAW_FRAMEBUFFER,draw);
    glUseProgram(program);glBindVertexArray(vao);glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D,texture);glBindSampler(0,sampler);glActiveTexture(active);
    glViewport(viewport[0],viewport[1],viewport[2],viewport[3]);glDepthMask(depthmask);glDepthFunc(depthfunc);
    glColorMask(colormask[0],colormask[1],colormask[2],colormask[3]);
    for(std::size_t i=0;i<caps.size();++i)if(enabled[i])glEnable(caps[i]);else glDisable(caps[i]);
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
void GlCopy::plane(unsigned source,const Texture& t,const View& v,bool depth){
  if(t.layers!=1||v.layer!=0||!glIsTexture(t.handle)||source==t.handle)
    throw std::runtime_error("Destination is not a shared 2D texture, or aliases the source");
  glBindTexture(GL_TEXTURE_2D,t.handle);
  GLint internal=0,w=0,h=0;glGetTexLevelParameteriv(GL_TEXTURE_2D,0,GL_TEXTURE_INTERNAL_FORMAT,&internal);
  glGetTexLevelParameteriv(GL_TEXTURE_2D,0,GL_TEXTURE_WIDTH,&w);glGetTexLevelParameteriv(GL_TEXTURE_2D,0,GL_TEXTURE_HEIGHT,&h);
  if(w!=static_cast<int>(t.width)||h!=static_cast<int>(t.height))throw std::runtime_error("SDK texture dimensions disagree with OpenGL");
  const bool nativeDepth=internal==GL_DEPTH_COMPONENT32F||internal==GL_DEPTH_COMPONENT24||internal==GL_DEPTH_COMPONENT16;
  if((depth&&!nativeDepth&&internal!=GL_R32F)||(!depth&&internal!=GL_RGBA8&&internal!=GL_SRGB8_ALPHA8))
    throw std::runtime_error("Unsupported SDK texture internal format: "+std::to_string(internal));
  glBindFramebuffer(GL_FRAMEBUFFER,fbo_);
  glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,0,0);
  glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER,GL_DEPTH_ATTACHMENT,GL_TEXTURE_2D,0,0);
  glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER,nativeDepth?GL_DEPTH_ATTACHMENT:GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,t.handle,0);
  glDrawBuffer(nativeDepth?GL_NONE:GL_COLOR_ATTACHMENT0);
  glReadBuffer(nativeDepth?GL_NONE:GL_COLOR_ATTACHMENT0);
  if(glCheckFramebufferStatus(GL_DRAW_FRAMEBUFFER)!=GL_FRAMEBUFFER_COMPLETE)throw std::runtime_error("Destination framebuffer is incomplete");
  if(nativeDepth){glEnable(GL_DEPTH_TEST);glDepthFunc(GL_ALWAYS);glDepthMask(GL_TRUE);}else{glDisable(GL_DEPTH_TEST);glDepthMask(GL_FALSE);}
  glViewport(std::min(v.x0,v.x1),std::min(v.y0,v.y1),width(v),height(v));
  glBindTexture(GL_TEXTURE_2D,source);
  glUniform2i(glGetUniformLocation(program_,"flipAxis"),v.x1<v.x0,v.y1<v.y0);
  glUniform1i(glGetUniformLocation(program_,"isDepth"),depth?1:0);
  glDrawArrays(GL_TRIANGLES,0,3);
  glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER,nativeDepth?GL_DEPTH_ATTACHMENT:GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,0,0);
}
void GlCopy::copy(const RenderedEye& s,const Frame& f,const EyeViews& v){
  (void)validate_stereo(f);
  if(v.color>=f.views.size()||v.depth>=f.views.size())throw std::invalid_argument("Missing copy view");
  State state;
  for(auto cap:state.caps)glDisable(cap);
  glColorMask(GL_TRUE,GL_TRUE,GL_TRUE,GL_TRUE);glUseProgram(program_);glBindVertexArray(vao_);
  glActiveTexture(GL_TEXTURE0);glBindSampler(0,0);glUniform1i(glGetUniformLocation(program_,"sourceImage"),0);
  const auto& c=f.views[v.color];const auto& d=f.views[v.depth];
  plane(s.color,f.textures[c.texture],c,false);plane(s.depth,f.textures[d.texture],d,true);
  const auto error=glGetError();if(error!=GL_NO_ERROR)throw std::runtime_error("OpenGL copy error: "+std::to_string(error));
}
void GlCopy::finish(){glFinish();}
}
