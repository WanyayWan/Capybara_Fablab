#pragma once

#include <stdbool.h>
#include <stddef.h>

// Decodes one application/x-www-form-urlencoded value: "%XX" becomes that byte and '+'
// becomes a space. A '%' not followed by two hex digits is copied as is.
// Returns false (out holds "") if the decoded text plus '\0' doesn't fit in out_size,
// or if it contains "%00".
// Pure C, no ESP-IDF includes, so it is host-tested in firmware/test.
bool url_decode(const char *in, char *out, size_t out_size);
