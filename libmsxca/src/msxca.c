/*
 * msxca - cross-platform decompressor for MS-XCA "LZXNATIVE" (magic 0FF512EE)
 * Xbox 360 xcompress blobs, as found inside LNK4 containers.
 *
 * Each blob is: 48-byte big-endian header, then a sequence of blocks.
 * Each block is: 4-byte big-endian CompressedBlockSize, then the compressed
 * data. The compressed data is CHUNK-FRAMED: it is a series of sub-chunks,
 * each preceded by a 2-byte big-endian length. A length prefix of 0xFF00
 * signals a 24-bit length (skip 1 byte, then read a 2-byte big-endian length);
 * a resulting zero length is the terminator. The 2-byte length prefixes must
 * be stripped before the bytes are fed to the libmspack LZX ("lzxd") decoder.
 *
 * Each block is an INDEPENDENT lzxd stream (fresh lzxd_init per block,
 * reset_interval = 0); the per-block decode length is UncompressedBlockSize
 * taken from the file header, NOT the 24-bit size field inside the stream.
 *
 * Built by compiling this file together with libmspack's lzxd.c
 * (readbits.h / readhuff.h / macros.h from the same source tree required).
 */

#include <stdlib.h>
#include <string.h>
#include "mspack.h"
#include "lzx.h"

typedef struct {
    const unsigned char *data;
    int size;
    int pos;
    int chunk_remaining;
} msxca_buf;

static struct mspack_file *msxca_open(struct mspack_system *self, const char *fn, int mode) {
    (void)self; (void)mode;
    /* lzxd_init receives the file handles directly and never calls open();
       if invoked, just echo the supplied handle back. */
    return (struct mspack_file*)fn;
}
static void msxca_close(struct mspack_file *f) { free(f); }

/* chunk-framed input reader: strips 2-byte big-endian length prefixes */
static int msxca_read(struct mspack_file *f, void *buf, int bytes) {
    msxca_buf *p = (msxca_buf*)f;
    unsigned char *out = (unsigned char*)buf;
    int got = 0;
    while (got < bytes) {
        if (p->pos >= p->size) break;
        if (p->chunk_remaining == 0) {
            if (p->pos + 2 > p->size) break;
            int size = (p->data[p->pos] << 8) | p->data[p->pos + 1];
            p->pos += 2;
            if ((size & 0xFF00) == 0xFF00) {
                p->pos += 1;
                if (p->pos + 2 > p->size) break;
                size = (p->data[p->pos] << 8) | p->data[p->pos + 1];
                p->pos += 2;
            }
            p->chunk_remaining = size;
        }
        int avail = p->size - p->pos;
        if (avail > p->chunk_remaining) avail = p->chunk_remaining;
        int n = bytes - got;
        if (n > avail) n = avail;
        if (n <= 0) break;
        memcpy(out, p->data + p->pos, (size_t)n);
        p->pos += n; p->chunk_remaining -= n; out += n; got += n;
    }
    return got;
}
static int msxca_write(struct mspack_file *f, void *buf, int bytes) {
    msxca_buf *p = (msxca_buf*)f;
    if (p->pos + bytes > p->size) bytes = p->size - p->pos;
    if (bytes < 0) bytes = 0;
    memcpy((void*)(p->data + p->pos), buf, (size_t)bytes);
    p->pos += bytes;
    return bytes;
}
static int msxca_seek(struct mspack_file *f, off_t offset, int mode) {
    msxca_buf *p = (msxca_buf*)f;
    if (mode == MSPACK_SYS_SEEK_START) p->pos = (int)offset;
    else if (mode == MSPACK_SYS_SEEK_CUR) p->pos += (int)offset;
    else p->pos = p->size + (int)offset;
    if (p->pos < 0) p->pos = 0;
    if (p->pos > p->size) p->pos = p->size;
    return 0;
}
static off_t msxca_tell(struct mspack_file *f) { return ((msxca_buf*)f)->pos; }
static void msxca_msg(struct mspack_file *f, const char *fmt, ...) { (void)f; (void)fmt; }
static void *msxca_alloc(struct mspack_system *s, size_t n) { (void)s; return malloc(n); }
static void msxca_sys_free(void *p) { free(p); }
static void msxca_copy(void *src, void *dst, size_t bytes) { memcpy(dst, src, bytes); }

static struct mspack_system g_sys = {
    msxca_open, msxca_close, msxca_read, msxca_write,
    msxca_seek, msxca_tell, msxca_msg, msxca_alloc, msxca_sys_free, msxca_copy
};

static unsigned rdBE32(const unsigned char *d, int o) {
    return (unsigned)((d[o] << 24) | (d[o+1] << 16) | (d[o+2] << 8) | d[o+3]);
}

/* Decompress a full xcompress blob.
 * On success returns 0, sets *out (malloc'd) and *outLen.
 * Caller must free *out with msxca_free(). */
int msxca_decompress(const unsigned char *blob, size_t blobLen,
                     unsigned char **out, size_t *outLen) {
    if (blobLen < 48) return -1;
    if (rdBE32(blob, 0) != 0x0FF512EE) return -2;

    unsigned windowSize = rdBE32(blob, 16);
    unsigned long long uncSize =
        ((unsigned long long)rdBE32(blob, 24) << 32) | rdBE32(blob, 28);
    unsigned largestChunk = rdBE32(blob, 40);

    unsigned char *output = (unsigned char*)malloc((size_t)uncSize);
    if (!output) return -3;

    int windowBits = 0;
    unsigned ws = windowSize;
    while ((ws & 1) == 0) { windowBits++; ws >>= 1; }

    long bo = 48;
    unsigned long long outPos = 0;
    int rc = 0;
    while ((size_t)bo < blobLen) {
        unsigned cbs = rdBE32(blob, (int)bo); bo += 4;
        if (cbs == 0) break;

        unsigned blockOut = largestChunk;
        if (uncSize - outPos < blockOut) blockOut = (unsigned)(uncSize - outPos);

        msxca_buf gin;
        gin.data = blob + bo; gin.size = (int)cbs; gin.pos = 0; gin.chunk_remaining = 0;
        msxca_buf gout;
        gout.data = output + outPos; gout.size = (int)blockOut; gout.pos = 0; gout.chunk_remaining = 0;

        struct lzxd_stream *lzx = lzxd_init(&g_sys,
            (struct mspack_file*)&gin, (struct mspack_file*)&gout,
            windowBits, 0, (int)cbs, (off_t)blockOut, 0);
        if (!lzx) { rc = -4; break; }
        int r = lzxd_decompress(lzx, (off_t)blockOut);
        lzxd_free(lzx);
        if (r != 0) { rc = -5; break; }

        bo += cbs;
        outPos += blockOut;
    }

    if (rc != 0 || outPos != uncSize) {
        free(output);
        return rc != 0 ? rc : -6;
    }
    *out = output;
    *outLen = (size_t)uncSize;
    return 0;
}

void msxca_free(unsigned char *p) { free(p); }
