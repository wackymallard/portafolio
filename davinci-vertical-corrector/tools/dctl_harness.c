/* Compiles VerticalLineCorrector.dctl as plain C and runs it on the CPU, so
 * the shader can be syntax-checked and rendered without Resolve.
 *
 *   cc -O2 -o harness tools/dctl_harness.c -lm
 *   ./harness in.rgbf out.rgbf W H tiltV tiltH roll amount fov zoom shiftX shiftY autofill edge guides
 *
 * Images are raw interleaved float32 RGB, top row first.
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct { float x, y; } float2;
typedef struct { float x, y, z; } float3;
static float2 make_float2(float x, float y) { float2 v = {x, y}; return v; }
static float3 make_float3(float x, float y, float z) { float3 v = {x, y, z}; return v; }

typedef struct { const float *d; int w, c; } Tex;
static float _tex2D(Tex t, int x, int y) { return t.d[(y * t.w + x) * 3 + t.c]; }

#define __DEVICE__ static
#define __TEXTURE__ Tex
#define _fabs fabsf
#define _fminf fminf
#define _fmaxf fmaxf
#define _floorf floorf
#define _sinf sinf
#define _cosf cosf
#define _tanf tanf

enum { EDGE_BLACK, EDGE_EXTEND, EDGE_MIRROR };
#define DCTLUI_SLIDER_FLOAT float
#define DCTLUI_CHECK_BOX int
#define DCTLUI_COMBO_BOX int
#define DEFINE_UI_PARAMS(name, label, type, def, ...) static type name = def;

#include "../VerticalLineCorrector.dctl"

int main(int argc, char **argv)
{
    if (argc != 16) {
        fprintf(stderr, "usage: see header\n");
        return 2;
    }
    int W = atoi(argv[3]), H = atoi(argv[4]);
    p_TiltV = atof(argv[5]);  p_TiltH = atof(argv[6]);  p_Roll = atof(argv[7]);
    p_Amount = atof(argv[8]); p_FOV = atof(argv[9]);    p_Zoom = atof(argv[10]);
    p_ShiftX = atof(argv[11]); p_ShiftY = atof(argv[12]);
    p_AutoFill = atoi(argv[13]); p_Edge = atoi(argv[14]); p_Guides = atoi(argv[15]);

    size_t n = (size_t)W * H * 3;
    float *in = malloc(n * sizeof(float)), *out = malloc(n * sizeof(float));
    FILE *f = fopen(argv[1], "rb");
    if (!f || fread(in, sizeof(float), n, f) != n) { fprintf(stderr, "read failed\n"); return 1; }
    fclose(f);

    Tex r = {in, W, 0}, g = {in, W, 1}, b = {in, W, 2};
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++) {
            float3 c = transform(W, H, x, y, r, g, b);
            float *o = out + ((size_t)y * W + x) * 3;
            o[0] = c.x; o[1] = c.y; o[2] = c.z;
        }

    f = fopen(argv[2], "wb");
    fwrite(out, sizeof(float), n, f);
    fclose(f);
    return 0;
}
