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
  for(bool floatColorDepth:{false,true})for(unsigned size:{128U,256U}){
    OwnedTextures owned;
    // Allocate in the SDK context, then render/copy on the VTK context.
    glfwMakeContextCurrent(renderer.sdk_window());glGenTextures(4,owned.ids.data());
    for(unsigned i=0;i<4;++i){glBindTexture(GL_TEXTURE_2D,owned.ids[i]);
      glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
      const bool depth=i%2==1;
      glTexImage2D(GL_TEXTURE_2D,0,depth?(floatColorDepth?GL_R32F:GL_DEPTH_COMPONENT32F):GL_RGBA8,size,size,0,
                   depth?(floatColorDepth?GL_RED:GL_DEPTH_COMPONENT):GL_RGBA,depth?GL_FLOAT:GL_UNSIGNED_BYTE,nullptr);
    }
    glFinish();renderer.make_current();
    Frame frame;
    for(auto id:owned.ids)frame.textures.push_back({id,size,size,1});
    // Deliberately reorder SDK view metadata and flip only the right image.
    frame.views={{Eye::right,Plane::depth,3,size,size,0,0,0},{Eye::left,Plane::color,0,0,0,size,size,0},
                 {Eye::right,Plane::color,2,size,size,0,0,0},{Eye::left,Plane::depth,1,0,0,size,size,0}};
    auto views=validate_stereo(frame);Clip clip{.1,10};Fov fov{-.6,.6,.6,-.6};
    for(int eye=0;eye<2;++eye){Pose p;p.position.z=2;p.position.x=eye==0?-.032:.032;
      auto s=renderer.render(p,fov,clip,size,size);
      // The copy must survive and restore a non-default host GL state.
      glEnable(GL_BLEND);glEnable(GL_SCISSOR_TEST);glScissor(0,0,1,1);
      glColorMask(GL_FALSE,GL_TRUE,GL_FALSE,GL_FALSE);glDepthMask(GL_FALSE);
      GLint oldProgram=0;glGetIntegerv(GL_CURRENT_PROGRAM,&oldProgram);
      copy.copy(s,frame,views[eye]);
      check(glIsEnabled(GL_BLEND)&&glIsEnabled(GL_SCISSOR_TEST),"GL capabilities not restored");
      GLboolean mask[4]{};glGetBooleanv(GL_COLOR_WRITEMASK,mask);check(!mask[0]&&mask[1]&&!mask[2]&&!mask[3],"write mask not restored");
      GLint newProgram=0;glGetIntegerv(GL_CURRENT_PROGRAM,&newProgram);check(oldProgram==newProgram,"program not restored");
      glDisable(GL_BLEND);glDisable(GL_SCISSOR_TEST);glColorMask(GL_TRUE,GL_TRUE,GL_TRUE,GL_TRUE);glDepthMask(GL_TRUE);
    }
    copy.finish();glfwMakeContextCurrent(renderer.sdk_window());
    // Readback is exclusively a test oracle, never part of the sender path.
    std::array<double,2> centroids{};
    for(int eye=0;eye<2;++eye){
      std::vector<unsigned char> rgba(size*size*4);std::vector<float> depth(size*size);
      glBindTexture(GL_TEXTURE_2D,owned.ids[eye*2]);glGetTexImage(GL_TEXTURE_2D,0,GL_RGBA,GL_UNSIGNED_BYTE,rgba.data());
      glBindTexture(GL_TEXTURE_2D,owned.ids[eye*2+1]);glGetTexImage(GL_TEXTURE_2D,0,floatColorDepth?GL_RED:GL_DEPTH_COMPONENT,GL_FLOAT,depth.data());
      double xsum=0;unsigned count=0;
      for(unsigned y=0;y<size;++y)for(unsigned x=0;x<size;++x){const auto i=y*size+x;
        check(std::isfinite(depth[i])&&depth[i]>=0&&depth[i]<=1,"invalid depth range");
        if(rgba[i*4+3]>128){check(rgba[i*4+1]>100,"cube color missing");xsum+=x+.5;++count;
          check(std::abs(depth[i]-depth_from_distance(1.8,clip))<.005,"front depth differs from analytic projection");}
      }
      check(count>100,"no visible cube pixels");centroids[eye]=xsum/count;
      check(depth.front()>.999F&&rgba[3]==0,"background depth or transparency corrupted");
    }
    // Undo the deliberate horizontal flip before comparing stereo disparity.
    check(centroids[0] > size-centroids[1]+1,"stereo eye order or horizontal flip wrong");
    renderer.make_current();check(glGetError()==GL_NO_ERROR,"GPU test left an OpenGL error");
    std::cout<<"PASS: "<<size<<" px, "<<(floatColorDepth?"R32F":"D32F")<<", shared contexts, stereo, depth, alpha, flips and GL state\n";
  }
  return 0;
}catch(const std::exception&e){std::cerr<<"ERROR: "<<e.what()<<'\n';return 1;}}
