#ifndef MSXCA_H
#define MSXCA_H

#ifdef __cplusplus
extern "C" {
#endif

/* Decompress a full MS-XCA "LZXNATIVE" xcompress blob (magic 0FF512EE).
 * On success returns 0, sets *out (malloc'd, free with msxca_free) and *outLen. */
#if defined(_WIN32) && !defined(__GNUC__)
#  define MSXCA_API __declspec(dllexport)
#else
#  define MSXCA_API __attribute__((visibility("default")))
#endif
MSXCA_API int msxca_decompress(const unsigned char *blob, size_t blobLen,
                               unsigned char **out, size_t *outLen);
MSXCA_API void msxca_free(unsigned char *p);

#ifdef __cplusplus
}
#endif

#endif
