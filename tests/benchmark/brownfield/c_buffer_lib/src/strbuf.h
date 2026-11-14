#ifndef LEGACY_STRBUF_H
#define LEGACY_STRBUF_H

#include <stddef.h>

typedef struct strbuf {
    char *data;
    size_t len;
    size_t cap;
} strbuf_t;

int strbuf_init(strbuf_t *sb, size_t initial_cap);
int strbuf_append(strbuf_t *sb, const char *text);
const char *strbuf_cstr(const strbuf_t *sb);
void strbuf_free(strbuf_t *sb);

#endif
