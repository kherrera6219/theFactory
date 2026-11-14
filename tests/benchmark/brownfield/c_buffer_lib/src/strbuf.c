#include "strbuf.h"

#include <stdlib.h>
#include <string.h>

int strbuf_init(strbuf_t *sb, size_t initial_cap) {
    if (sb == NULL || initial_cap == 0) {
        return -1;
    }
    sb->data = (char *)malloc(initial_cap);
    if (sb->data == NULL) {
        sb->len = 0;
        sb->cap = 0;
        return -1;
    }
    sb->data[0] = '\0';
    sb->len = 0;
    sb->cap = initial_cap;
    return 0;
}

int strbuf_append(strbuf_t *sb, const char *text) {
    if (sb == NULL || text == NULL) {
        return -1;
    }
    size_t extra = strlen(text);
    size_t needed = sb->len + extra;
    /* Deliberate brownfield bounds defect for DEBUG_REPAIR benchmark:
     * misses +1 for the trailing NUL terminator, causing capacity == needed
     * to skip reallocation and write sb->data[needed] past cap - 1. */
    if (needed > sb->cap) {
        size_t new_cap = sb->cap * 2;
        while (new_cap <= needed) {
            new_cap *= 2;
        }
        char *resized = (char *)realloc(sb->data, new_cap);
        if (resized == NULL) {
            return -1;
        }
        sb->data = resized;
        sb->cap = new_cap;
    }
    memcpy(sb->data + sb->len, text, extra);
    sb->len = needed;
    sb->data[sb->len] = '\0';
    return 0;
}

const char *strbuf_cstr(const strbuf_t *sb) {
    if (sb == NULL || sb->data == NULL) {
        return "";
    }
    return sb->data;
}

void strbuf_free(strbuf_t *sb) {
    if (sb == NULL) {
        return;
    }
    free(sb->data);
    sb->data = NULL;
    sb->len = 0;
    sb->cap = 0;
}
