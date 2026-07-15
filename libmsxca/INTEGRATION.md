# Integrating libmsxca into your project

## C/C++ projects

### Linking as a shared library

1. Build libmsxca (see [BUILDING.md](BUILDING.md))
2. Link against the shared library:

```sh
gcc myapp.c -lmsxca -Lpath/to/build -Ipath/to/libmsxca/src -o myapp
```

Or in CMake:

```cmake
add_subdirectory(path/to/libmsxca)
target_link_libraries(myapp PRIVATE msxca)
target_include_directories(myapp PRIVATE path/to/libmsxca/src)
```

### Using the API

```c
#include "msxca.h"
#include <stdlib.h>

// Decompress a blob
unsigned char *blob = /* ... your compressed data ... */;
size_t blobLen = /* ... its length ... */;

unsigned char *output = NULL;
size_t outputLen = 0;

int result = msxca_decompress(blob, blobLen, &output, &outputLen);

if (result == 0) {
    // output contains the decompressed data (outputLen bytes)
    // ...

    // Free when done
    msxca_free(output);
} else {
    // Error codes:
    //   -1: blob too short (< 48 bytes)
    //   -2: wrong magic (not 0FF512EE)
    //   -3: out of memory
    //   -4: lzxd_init failed
    //   -5: lzxd_decompress failed
    //   -6: output length mismatch
}
```

## .NET / C# projects (P/Invoke)

1. Build `msxca.dll` (Windows) or `libmsxca.so` (Linux) or `libmsxca.dylib` (macOS)
2. Place the native library where .NET can find it:
   - Next to your assembly, or
   - In `runtimes/<rid>/native/` (NuGet convention)

```csharp
using System.Runtime.InteropServices;

internal static class MsXcaInterop
{
    [DllImport("msxca", CallingConvention = CallingConvention.Cdecl)]
    private static extern int msxca_decompress(
        byte[] blob, UIntPtr blobLen,
        out IntPtr output, out UIntPtr outputLen);

    [DllImport("msxca", CallingConvention = CallingConvention.Cdecl)]
    private static extern void msxca_free(IntPtr p);

    public static byte[] Decompress(byte[] blob)
    {
        int rc = msxca_decompress(blob, (UIntPtr)blob.Length,
                                   out IntPtr ptr, out UIntPtr len);
        if (rc != 0) throw new Exception($"msxca_decompress failed: {rc}");
        byte[] result = new byte[(int)len];
        Marshal.Copy(ptr, result, 0, result.Length);
        msxca_free(ptr);
        return result;
    }
}
```

### .NET NuGet-style runtime layout

For cross-platform .NET apps, place the native library in the RID-specific
native folder so the runtime loader finds it automatically:

```
runtimes/
  win-x64/native/msxca.dll
  linux-x64/native/libmsxca.so
  osx-x64/native/libmsxca.dylib
  osx-arm64/native/libmsxca.dylib
```

Then use `NativeLibrary.SetDllImportResolver()` or let .NET's default
probe find it. A minimal `.csproj` example:

```xml
<ItemGroup>
    <Content Include="runtimes\win-x64\native\msxca.dll"
             CopyToOutputDirectory="PreserveNewest"
             Link="runtimes\win-x64\native\msxca.dll" />
    <Content Include="runtimes\linux-x64\native\libmsxca.so"
             CopyToOutputDirectory="PreserveNewest"
             Link="runtimes\linux-x64\native\libmsxca.so" />
    <Content Include="runtimes\osx-x64\native\libmsxca.dylib"
             CopyToOutputDirectory="PreserveNewest"
             Link="runtimes\osx-x64\native\libmsxca.dylib" />
</ItemGroup>
```

## Important notes

- **Thread safety**: The library is safe to use from multiple threads, provided
  each thread uses its own `blob` / `output` / `outputLen` variables. The
  library allocates memory internally; `msxca_free()` frees it.
- **No compression**: This library only decompresses. There is no cross-platform
  `LZXNATIVE` encoder. Recompression requires `xcompress.dll` on Windows.
- **Input validation**: `msxca_decompress` validates the magic number
  (`0FF512EE`) and returns -2 for non-LZXNATIVE data.
