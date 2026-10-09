#pragma once
#include "qarvtk/layout.hpp"
#include "qarvtk/renderer.hpp"
namespace qarvtk {
// Two shader copies per eye. No pixel readback, no PBO/CPU fallback.
// Destruction requires the render context to be current.
class GlCopy {
public:
  GlCopy();~GlCopy();
  GlCopy(const GlCopy&)=delete;GlCopy& operator=(const GlCopy&)=delete;
  void copy(const RenderedEye& source,const Frame& target,const EyeViews& views);
  void finish(); // Conservative cross-context completion before SDK show_frame.
private:
  unsigned program_{},vao_{},fbo_{};
  void plane(unsigned source,const Texture& texture,const View& view,bool depth);
};
}
