#include "../apps/wgl_callbacks.hpp"
#include <iostream>

void require(bool value, const char* message) {
  if (!value) throw std::runtime_error(message);
}
struct Context {
  HWND window{}; HDC dc{}; HGLRC context{};
  Context() {
    WNDCLASSW wc{}; wc.style=CS_OWNDC; wc.lpfnWndProc=DefWindowProcW;
    wc.hInstance=GetModuleHandleW(nullptr); wc.lpszClassName=L"QarvtkWglCallbackTest";
    if (!RegisterClassW(&wc) && GetLastError()!=ERROR_CLASS_ALREADY_EXISTS)
      throw std::runtime_error("Cannot register WGL test window class");
    try {
      window=CreateWindowExW(0,wc.lpszClassName,L"WGL callback test",WS_OVERLAPPEDWINDOW,
                             0,0,32,32,nullptr,nullptr,wc.hInstance,nullptr);
      require(window!=nullptr,"Cannot create hidden WGL test window");
      dc=GetDC(window); require(dc!=nullptr,"Cannot obtain WGL test DC");
      PIXELFORMATDESCRIPTOR pfd{}; pfd.nSize=sizeof(pfd); pfd.nVersion=1;
      pfd.dwFlags=PFD_DRAW_TO_WINDOW|PFD_SUPPORT_OPENGL|PFD_DOUBLEBUFFER;
      pfd.iPixelType=PFD_TYPE_RGBA; pfd.cColorBits=24; pfd.cDepthBits=24;
      const int pixel=ChoosePixelFormat(dc,&pfd);
      require(pixel!=0 && SetPixelFormat(dc,pixel,&pfd),"Cannot set WGL test pixel format");
      context=wglCreateContext(dc); require(context!=nullptr,"Cannot create basic WGL test context");
    } catch (...) { close(); throw; }
  }
  void close() {
    if (context) { if (wglGetCurrentContext()==context) wglMakeCurrent(nullptr,nullptr); wglDeleteContext(context); context=nullptr; }
    if (dc) { ReleaseDC(window,dc); dc=nullptr; }
    if (window) { DestroyWindow(window); window=nullptr; }
  }
  ~Context() { close(); }
};
int main() { try {
  Context host, sdk;
  require(wglMakeCurrent(host.dc,host.context)!=FALSE,"Cannot bind host context");
  qarvtk::WglCallbacks callbacks(sdk.dc,sdk.context);
  auto params=qar_stream_params_opengl_default(); callbacks.configure(params);
  // Test worker migration and OpenGL 1.1 export fallback using Windows' basic
  // context. This does not claim glGetStringi or NVIDIA interop support in CI.
  const auto probe=callbacks.probe_on_worker();
  require(!probe.version.empty(),"Worker could not query its own GL version");
  require(wglGetCurrentContext()==host.context,"Worker disturbed host thread context");
  require(params.get_proc_address(params.user_state,"glGetString")==nullptr,
          "Resolved against the wrong context");
  const auto before=params.capture_current(params.user_state);
  require(before.has_context && before.context==host.context,"Host binding was not captured");
  require(params.make_current(params.user_state),"Callback did not bind SDK context");
  require(wglGetCurrentContext()==sdk.context,"SDK context is not current");
  require(params.get_proc_address(params.user_state,"glGetString")!=nullptr,
          "OpenGL 1.1 export fallback failed");
  require(params.get_proc_address(params.user_state,"qarvtkNonexistentGlFunction")==nullptr,
          "Invalid function returned an address");
  require(params.restore_current(params.user_state,&before),"Host restore failed");
  require(wglGetCurrentContext()==host.context && wglGetCurrentDC()==host.dc,"Wrong host binding restored");
  require(params.unbind(params.user_state),"Unbind failed");
  const auto empty=params.capture_current(params.user_state);
  require(!empty.has_context,"Empty binding reported as current");
  require(params.make_current(params.user_state),"Rebind failed");
  require(params.restore_current(params.user_state,&empty) && wglGetCurrentContext()==nullptr,
          "Empty binding was not restored");
  std::cout << "PASS: native WGL worker binding, export loading, host restore and unbind; GL " << probe.version << '\n';
  return 0;
} catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; } }
