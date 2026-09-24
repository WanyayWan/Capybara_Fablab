// Host unit tests for url_decode.c (portal form fields: Wi-Fi and backend URL).
// Build and run: make -C firmware/test

#include <stdio.h>
#include <string.h>

#include "url_decode.h"

static int failures;
static int total;

static void check(const char *name, const char *in, size_t out_size, bool want_ok, const char *want)
{
    char out[256];
    memset(out, 'x', sizeof(out));
    ++total;
    bool ok = url_decode(in, out, out_size);
    if (ok != want_ok || strcmp(out, want) != 0) {
        printf("FAIL %s: got %s \"%s\", want %s \"%s\"\n", name, ok ? "true" : "false", out,
               want_ok ? "true" : "false", want);
        ++failures;
    } else {
        printf("ok   %s\n", name);
    }
}

int main(void)
{
    check("U1 plain", "fabai123", 64, true, "fabai123");
    check("U2 backend url", "http%3A%2F%2F192.168.137.1%3A8000", 128, true, "http://192.168.137.1:8000");
    check("U3 raw url (curl fallback)", "http://192.168.137.1:8000", 128, true, "http://192.168.137.1:8000");
    check("U4 plus is space", "My+Hotspot", 33, true, "My Hotspot");
    check("U5 encoded plus stays plus", "a%2Bb", 16, true, "a+b");
    check("U6 percent sign", "100%25sure", 16, true, "100%sure");
    check("U7 symbols password", "p%40ss%26w%3Drd%21", 65, true, "p@ss&w=rd!");
    check("U8 lower-case hex", "%3a%2f", 8, true, ":/");
    check("U9 malformed % at end", "abc%", 16, true, "abc%");
    check("U10 malformed %X at end", "abc%4", 16, true, "abc%4");
    check("U11 malformed %G1", "a%G1b", 16, true, "a%G1b");
    check("U12 empty", "", 4, true, "");
    check("U13 exact fit", "abc", 4, true, "abc");
    check("U14 too long", "abcd", 4, false, "");
    check("U15 fits after decoding", "%41%42%43", 4, true, "ABC");
    check("U16 %00 rejected", "ab%00cd", 16, false, "");

    if (failures) {
        printf("%d of %d url_decode tests FAILED\n", failures, total);
        return 1;
    }
    printf("%d url_decode tests passed\n", total);
    return 0;
}
