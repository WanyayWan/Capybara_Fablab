#include "url_decode.h"

static int hex_value(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

bool url_decode(const char *in, char *out, size_t out_size)
{
    if (!in || !out || out_size == 0) return false;
    size_t n = 0;
    for (size_t i = 0; in[i]; ++i) {
        char c = in[i];
        if (c == '+') {
            c = ' ';
        } else if (c == '%') {
            int hi = hex_value(in[i + 1]);
            int lo = hi < 0 ? -1 : hex_value(in[i + 2]);  // in[i + 1] is not '\0' when hi >= 0
            if (lo >= 0) {
                c = (char)(hi * 16 + lo);
                i += 2;
            }
        }
        if (c == '\0' || n + 1 >= out_size) {  // "%00" would silently cut the value short
            out[0] = '\0';
            return false;
        }
        out[n++] = c;
    }
    out[n] = '\0';
    return true;
}
