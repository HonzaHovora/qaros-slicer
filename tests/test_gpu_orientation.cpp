#include "qarvtk/gl.hpp"
#include "qarvtk/gl_copy.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <vector>
using namespace qarvtk;
namespace {
constexpr unsigned w=160,h=128,tw=192,th=160,ox=11,oy=17;
void check(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
struct Textures {
  std::array<unsigned,4> ids{};
  ~Textures(){glDeleteTextures(4,ids.data());}
};
// Independent ray/box oracle: the renderer's default cube occupies +/-0.2 m.
// The ray is parameterized by forward camera distance, not Euclidean length.
double hit_cube(Vec3 origin,Vec3 direction){
  const std::array<double,3> o{origin.x,origin.y,origin.z},d{direction.x,direction.y,direction.z};
  double enter=0,leave=100;
  for(int axis=0;axis<3;++axis){
    if(std::abs(d[axis])<1e-12){if(std::abs(o[axis])>.2)return -1;continue;}
    const double a=(-.2-o[axis])/d[axis],b=(.2-o[axis])/d[axis];
    enter=std::max(enter,std::min(a,b));leave=std::min(leave,std::max(a,b));
  }
  return leave>enter&&enter>0?enter:-1;
}
std::size_t address(const View& v,unsigned x,unsigned y){
  const unsigned tx=std::min(v.x0,v.x1)+(v.x1>v.x0?x:w-1-x);
  const unsigned ty=std::min(v.y0,v.y1)+(v.y1>v.y0?y:h-1-y);
  return ty*tw+tx;
}
}
int main(){try{
  Renderer renderer;GlCopy copy;Clip clip{.1,10};
  // Off-centre frustum and camera translations make a vertical mirror visible.
  Fov fov{-.50,.62,.55,-.45};
  const std::array<Pose,7> cameras{{
    {{.06,.10,2},{}},
    {{.06,.10,2},{std::sin(.07),0,0,std::cos(.07)}}, // pitch up
    {{.06,.10,2},{-std::sin(.07),0,0,std::cos(.07)}}, // pitch down
    {{.06,.10,2},{0,std::sin(.07),0,std::cos(.07)}}, // yaw left
    {{.06,.10,2},{0,-std::sin(.07),0,std::cos(.07)}}, // yaw right
    {{.06,.10,2},{0,0,std::sin(.12),std::cos(.12)}}, // roll
    {{-.08,-.12,2},{}}
  }};
  for(GLenum target:{GL_TEXTURE_2D,GL_TEXTURE_2D_ARRAY})for(bool floatDepth:{false,true}){
    Textures textures;glfwMakeContextCurrent(renderer.sdk_window());glGenTextures(4,textures.ids.data());
    for(unsigned i=0;i<4;++i){
      const bool depth=i%2;const auto internal=depth?(floatDepth?GL_R32F:GL_DEPTH_COMPONENT32F):GL_RGBA8;
      const auto format=depth?(floatDepth?GL_RED:GL_DEPTH_COMPONENT):GL_RGBA;
      glBindTexture(target,textures.ids[i]);
      glTexParameteri(target,GL_TEXTURE_MIN_FILTER,GL_NEAREST);glTexParameteri(target,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
      if(target==GL_TEXTURE_2D_ARRAY)glTexImage3D(target,0,internal,tw,th,1,0,format,depth?GL_FLOAT:GL_UNSIGNED_BYTE,nullptr);
      else glTexImage2D(target,0,internal,tw,th,0,format,depth?GL_FLOAT:GL_UNSIGNED_BYTE,nullptr);
    }
    glFinish();renderer.make_current();
    Frame frame;for(auto id:textures.ids)frame.textures.push_back({id,tw,th,1});
    // Reordered views, a padded subrectangle and DIFFERENT flips per plane.
    frame.views={{Eye::right,Plane::depth,3,ox,oy+h,ox+w,oy,0},
                 {Eye::left,Plane::color,0,ox,oy,ox+w,oy+h,0},
                 {Eye::right,Plane::color,2,ox+w,oy+h,ox,oy,0},
                 {Eye::left,Plane::depth,1,ox+w,oy,ox,oy+h,0}};
    const auto eyes=validate_stereo(frame);
    for(const auto& camera:cameras){
      std::array<Pose,2> poses{camera,camera};
      for(unsigned eye=0;eye<2;++eye){poses[eye].position.x+=eye?.032:-.032;
        auto source=renderer.render(poses[eye],fov,clip,w,h);copy.copy(source,frame,eyes[eye]);}
      copy.finish();glfwMakeContextCurrent(renderer.sdk_window());
      for(unsigned eye=0;eye<2;++eye){
        std::vector<unsigned char> rgba(tw*th*4);std::vector<float> depth(tw*th);
        glBindTexture(target,textures.ids[eye*2]);glGetTexImage(target,0,GL_RGBA,GL_UNSIGNED_BYTE,rgba.data());
        glBindTexture(target,textures.ids[eye*2+1]);
        glGetTexImage(target,0,floatDepth?GL_RED:GL_DEPTH_COMPONENT,GL_FLOAT,depth.data());
        const auto& cv=frame.views[eyes[eye].color];const auto& dv=frame.views[eyes[eye].depth];
        unsigned visible=0,wrongMask=0;
        for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x){
          const double u=(x+.5)/w,v=(y+.5)/h;
          // Row zero is TOP: positive view-space Y maps toward smaller rows.
          const Vec3 ray{std::tan(fov.left)+(std::tan(fov.right)-std::tan(fov.left))*u,
                         std::tan(fov.up)+(std::tan(fov.down)-std::tan(fov.up))*v,-1};
          const double distance=hit_cube(poses[eye].position,rotate(poses[eye].orientation,ray));
          const auto ci=address(cv,x,y)*4,di=address(dv,x,y);
          const bool drawn=rgba[ci+3]>128,expected=distance>0;
          if(drawn!=expected){++wrongMask;continue;}
          if(expected){++visible;check(rgba[ci+1]>100,"cube color missing");
            check(std::abs(depth[di]-depth_from_distance(distance,clip))<.00005,
                  "depth does not reconstruct the stationary cube at this pose");}
          else check(depth[di]>.9999,"background color/depth orientation differs");
        }
        check(visible>100,"cube outside orientation test view");
        check(wrongMask<12,"stream image is mirrored or camera pose/FOV disagrees with the volume");
      }
      renderer.make_current();check(glGetError()==GL_NO_ERROR,"orientation test left a GL error");
    }
    std::cout<<"PASS: stationary cube, pitch/yaw/roll, translations, asymmetric FOV, per-plane flips, "
      <<(target==GL_TEXTURE_2D_ARRAY?"2D array":"2D")<<", "<<(floatDepth?"R32F":"D32F")<<'\n';
  }
  return 0;
}catch(const std::exception& e){std::cerr<<"ERROR: "<<e.what()<<'\n';return 1;}}
