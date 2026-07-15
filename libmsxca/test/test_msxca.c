#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "msxca.h"

static unsigned char *load_file(const char *path, long *outlen){
    FILE *f=fopen(path,"rb"); if(!f) return NULL;
    fseek(f,0,SEEK_END); long fs=ftell(f); fseek(f,0,SEEK_SET);
    unsigned char *b=malloc(fs); if(fread(b,1,fs,f)!=(size_t)fs){free(b);fclose(f);return NULL;}
    fclose(f); *outlen=fs; return b;
}
static unsigned rdLE32(const unsigned char *d, int o){return d[o]|(d[o+1]<<8)|(d[o+2]<<16)|(d[o+3]<<24);}
static unsigned rdBE32(const unsigned char *d, int o){return (d[o]<<24)|(d[o+1]<<16)|(d[o+2]<<8)|d[o+3];}

int main(void){
    const char *datPath="/mnt/nvme0n1p1/newproject3/testdata/lnk4/elevene-system.dat";
    unsigned char *d; long fs;
    if(!(d=load_file(datPath,&fs))){ printf("cannot load dat\n"); return 1; }
    unsigned dataOffset = rdLE32(d,4);
    int pass=0, fail=0;
    for(int fid=0; fid<200; fid++){
        int off=8, cur=0; unsigned char *blob=NULL; long blen=0; int found=0;
        while(off+8<=fs){
            unsigned sb=rdLE32(d,off); off+=4;
            unsigned lb=rdLE32(d,off); off+=4;
            if(sb==0&&lb==0) break;
            long pos=((long)sb<<11)+dataOffset;
            long length=((long)lb<<10);
            if(pos+8>fs) break;
            if(rdBE32(d,pos)==0x0FF512EE){
                if(cur==fid){ blob=malloc(length); memcpy(blob,d+pos,length); blen=length; found=1; break; }
                cur++;
            }
        }
        if(!found) break;
        unsigned char *out=NULL; size_t outLen=0;
        int rc = msxca_decompress(blob, blen, &out, &outLen);
        char wn[256]; sprintf(wn,"/tmp/opencode/dec2/fid%03d.bin", fid);
        if(rc==0 && out){
            FILE *wf=fopen(wn,"wb"); if(wf){ fwrite(out,1,outLen,wf); fclose(wf); }
            pass++;
        } else {
            printf("fid %d: rc=%d FAILED\n", fid, rc);
            fail++;
        }
        free(blob); if(out) msxca_free(out);
    }
    printf("RESULT rc_ok=%d rc_fail=%d\n", pass, fail);
    return 0;
}
