#include "qarvtk/gl.hpp"
#include "qarvtk/gl_copy.hpp"
#include <array>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <vector>
using namespace qarvtk;
void check(bool good,const char*message){if(!good)throw std::runtime_error(message);}
struct OwnedTextures {
  std::array<unsigned,4> ids{};
  ~OwnedTextures(){glDeleteTextures(4,ids.data());}
};
int main(){try{
  Renderer renderer;std::cout<<renderer.capabilities()<<'\n';
  GlCopy copy;
  for(GLenum target:{GL_TEXTURE_2D,GL_TEXTURE_2D_ARRAY})
  for(bool floatColorDepth:{false,true})for(auto size:{std::array<unsigned,2>{128,128},{1920,1080}}){
    const auto width=size[0],height=size[1];
    OwnedTextures owned;
    // Allocate in the SDK context, then render/copy on the VTK context.
    glfwMakeContextCurrent(renderer.sdk_window());glGenTextures(4,owned.ids.data());
    for(unsigned i=0;i<4;++i){glBindTexture(target,owned.ids[i]);
      glTexParameteri(target,GL_TEXTURE_MIN_FILTER,GL_NEAREST);glTexParameteri(target,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
      const bool depth=i%2==1;
      const auto internal=depth?(floatColorDepth?GL_R32F:GL_DEPTH_COMPONENT32F):GL_RGBA8;
      const auto format=depth?(floatColorDepth?GL_RED:GL_DEPTH_COMPONENT):GL_RGBA;
      if(target==GL_TEXTURE_2D_ARRAY)
        glTexImage3D(target,0,internal,width,height,1,0,format,depth?GL_FLOAT:GL_UNSIGNED_BYTE,nullptr);
      else glTexImage2D(target,0,internal,width,height,0,format,depth?GL_FLOAT:GL_UNSIGNED_BYTE,nullptr);
    }
    glFinish();renderer.make_current();
    Frame frame;
    for(auto id:owned.ids)frame.textures.push_back({id,width,height,1});
    // Deliberately reorder SDK view metadata and flip only the right image.
    frame.views={{Eye::right,Plane::depth,3,width,height,0,0,0},{Eye::left,Plane::color,0,0,0,width,height,0},
                 {Eye::right,Plane::color,2,width,height,0,0,0},{Eye::left,Plane::depth,1,0,0,width,height,0}};
    auto views=validate_stereo(frame);Clip clip{.1,10};Fov fov{-.6,.6,.6,-.6};
    for(int eye=0;eye<2;++eye){Pose p;p.position.z=2;p.position.x=eye==0?-.032:.032;p.position.y=.12;
      auto s=renderer.render(p,fov,clip,width,height);
      // The copy must survive and restore a non-default host GL state.
      glEnable(GL_BLEND);glEnable(GL_SCISSOR_TEST);glScissor(0,0,1,1);
      glColorMask(GL_FALSE,GL_TRUE,GL_FALSE,GL_FALSE);glDepthMask(GL_FALSE);
      GLint oldProgram=0;glGetIntegerv(GL_CURRENT_PROGRAM,&oldProgram);
      glActiveTexture(GL_TEXTURE0);
      // Leave a same-sized 2D texture bound: the old unchecked bind could query
      // this stale object after trying to bind a one-layer array as 2D.
      glBindTexture(GL_TEXTURE_2D,s.color);
      if(target==GL_TEXTURE_2D_ARRAY)glBindTexture(target,owned.ids[2]);
      GLint oldArray=0;glGetIntegerv(GL_TEXTURE_BINDING_2D_ARRAY,&oldArray);
      glActiveTexture(GL_TEXTURE3);
      copy.copy(s,frame,views[eye]);
      check(glIsEnabled(GL_BLEND)&&glIsEnabled(GL_SCISSOR_TEST),"GL capabilities not restored");
      GLboolean mask[4]{};glGetBooleanv(GL_COLOR_WRITEMASK,mask);check(!mask[0]&&mask[1]&&!mask[2]&&!mask[3],"write mask not restored");
      GLint newProgram=0;glGetIntegerv(GL_CURRENT_PROGRAM,&newProgram);check(oldProgram==newProgram,"program not restored");
      GLint active=0,texture=0;glGetIntegerv(GL_ACTIVE_TEXTURE,&active);check(active==GL_TEXTURE3,"active texture not restored");
      glActiveTexture(GL_TEXTURE0);glGetIntegerv(GL_TEXTURE_BINDING_2D,&texture);
      check(texture==static_cast<GLint>(s.color),"2D texture binding not restored");
      glGetIntegerv(GL_TEXTURE_BINDING_2D_ARRAY,&texture);check(texture==oldArray,"array texture binding not restored");
      glBindTexture(GL_TEXTURE_2D_ARRAY,0);glBindTexture(GL_TEXTURE_2D,0);
      glDisable(GL_BLEND);glDisable(GL_SCISSOR_TEST);glColorMask(GL_TRUE,GL_TRUE,GL_TRUE,GL_TRUE);glDepthMask(GL_TRUE);
    }
    copy.finish();glfwMakeContextCurrent(renderer.sdk_window());
    // Readback is exclusively a test oracle, never part of the sender path.
    std::array<double,2> centroids{};
    for(int eye=0;eye<2;++eye){
      std::vector<unsigned char> rgba(width*height*4);std::vector<float> depth(width*height);
      glBindTexture(target,owned.ids[eye*2]);glGetTexImage(target,0,GL_RGBA,GL_UNSIGNED_BYTE,rgba.data());
      glBindTexture(target,owned.ids[eye*2+1]);glGetTexImage(target,0,floatColorDepth?GL_RED:GL_DEPTH_COMPONENT,GL_FLOAT,depth.data());
      double xsum=0,ysum=0;unsigned count=0;
      for(unsigned y=0;y<height;++y)for(unsigned x=0;x<width;++x){const auto i=y*width+x;
        check(std::isfinite(depth[i])&&depth[i]>=0&&depth[i]<=1,"invalid depth range");
        if(rgba[i*4+3]>128){check(rgba[i*4+1]>30 && rgba[i*4+1]>rgba[i*4],"cube color missing");xsum+=x+.5;ysum+=y+.5;++count;
          check(std::abs(depth[i]-depth_from_distance(1.8,clip))<.005,"front depth differs from analytic projection");}
      }
      check(count>100,"no visible cube pixels");centroids[eye]=xsum/count;
      const double streamY=eye==0?ysum/count:height-ysum/count;
      check(streamY>height*.53,"camera above cube must place it below centre in the top-down stream");
      check(depth.front()>.999F&&rgba[3]==0,"background depth or transparency corrupted");
    }
    // Undo the deliberate horizontal flip before comparing stereo disparity.
    check(centroids[0] > width-centroids[1]+1,"stereo eye order or horizontal flip wrong");
    renderer.make_current();check(glGetError()==GL_NO_ERROR,"GPU test left an OpenGL error");
    std::cout<<"PASS: "<<width<<'x'<<height<<" px, "<<(target==GL_TEXTURE_2D_ARRAY?"2D array":"2D")
      <<", "<<(floatColorDepth?"R32F":"D32F")<<", shared contexts, stereo, depth, alpha, flips and GL state\n";
  }
  return 0;
}catch(const std::exception&e){std::cerr<<"ERROR: "<<e.what()<<'\n';return 1;}}
