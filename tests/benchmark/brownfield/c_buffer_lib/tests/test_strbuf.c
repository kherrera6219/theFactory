#include "../src/strbuf.h"

#include <assert.h>
#include <string.h>

int main(void) {
    strbuf_t sb;
    assert(strbuf_init(&sb, 4) == 0);
    assert(strbuf_append(&sb, "hi") == 0);
    assert(strcmp(strbuf_cstr(&sb), "hi") == 0);

    /* Exact capacity boundary: len(2) + extra(2) + NUL(1) = 5 > cap(4). */
    assert(strbuf_append(&sb, "ya") == 0);
    assert(sb.cap > sb.len);
    assert(strcmp(strbuf_cstr(&sb), "hiya") == 0);

    strbuf_free(&sb);
    return 0;
}
