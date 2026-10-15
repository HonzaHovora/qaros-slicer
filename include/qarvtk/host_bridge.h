#pragma once
#include <stdint.h>
#ifdef _WIN32
#define QARVTK_HOST_API __declspec(dllexport)
#else
#define QARVTK_HOST_API
#endif
#ifdef __cplusplus
extern "C" {
#endif

typedef struct QarvtkHost QarvtkHost;
typedef struct QarvtkHostEye {
  double position[3], orientation[4], fov[4]; /* x/y/z/w; left/right/up/down */
  uint32_t width, height;
} QarvtkHostEye;
typedef struct QarvtkHostFrame {
  uint64_t serial;
  QarvtkHostEye eyes[2];
} QarvtkHostFrame;

/* ABI 1, Windows x64/session SDK only. All calls are on the creating GUI thread.
   poll: 0 waiting, 1 frame leased, 2 stopped, -1 error (message via status).
   Stop is asynchronous; destroy returns 0 until the worker is finished.
   No borrowed GPU texture survives color/depth returning. SDK frame ownership
   remains leased until finish or stop. Never unload this DLL with live handles. */
QARVTK_HOST_API const char* qarvtk_host_info(void);
QARVTK_HOST_API int qarvtk_host_create(const char* sdk_root,const char* target,const char* log_folder,
                                     QarvtkHost** result,char* error,uint32_t error_size);
QARVTK_HOST_API int qarvtk_host_poll(QarvtkHost*,QarvtkHostFrame*);
QARVTK_HOST_API int qarvtk_host_color(QarvtkHost*,uint64_t serial,uint32_t eye,
                                     uint32_t color,uint32_t depth,uint32_t width,uint32_t height);
QARVTK_HOST_API int qarvtk_host_depth(QarvtkHost*,uint64_t serial,uint32_t eye,
                                     uint32_t color,uint32_t depth,uint32_t volume_color,uint32_t volume_depth,
                                     uint32_t width,uint32_t height);
QARVTK_HOST_API int qarvtk_host_finish(QarvtkHost*,uint64_t serial);
QARVTK_HOST_API void qarvtk_host_stop(QarvtkHost*);
QARVTK_HOST_API int qarvtk_host_destroy(QarvtkHost*);
QARVTK_HOST_API void qarvtk_host_status(QarvtkHost*,char* text,uint32_t size);

#ifdef __cplusplus
}
#endif
