/* Research-only C11 owned UTF-8 String handles, independent of Value IR.
 * Each handle holds a strong reference; slices retain the owner.
 * Not thread safe. Manual C copies without retain are unsafe.
 */
#include "owned_string.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

struct sh_owned_buffer {
    size_t refs;
    size_t bytes;
    unsigned char data[];
};

static size_t sh_live_bytes = 0;
static size_t sh_live_objects = 0;

static void sh_owned_fail(const char *message) {
    fprintf(stderr, "Samhus owned String experiment: %s\n", message);
    exit(2);
}

static sh_owned sh_empty(void) {
    return (sh_owned){NULL, 0, 0};
}

static const unsigned char *sh_data(sh_owned value) {
    return value.owner ? value.owner->data + value.offset : NULL;
}

/* Reject overlong UTF-8, surrogates, NUL, truncated and >U+10FFFF. */
static size_t sh_utf8_step(const unsigned char *data, size_t size, size_t i) {
    unsigned char a = data[i];
    if (a >= 0x01 && a <= 0x7f) return 1;
    if (a == 0) sh_owned_fail("NUL byte is unsupported");
    size_t count = 0;
    if (a >= 0xc2 && a <= 0xdf) count = 2;
    else if (a >= 0xe0 && a <= 0xef) count = 3;
    else if (a >= 0xf0 && a <= 0xf4) count = 4;
    else sh_owned_fail("Invalid UTF-8");
    if (count > size - i) sh_owned_fail("Invalid UTF-8");
    unsigned char b = data[i+1];
    if (b < 0x80 || b > 0xbf) sh_owned_fail("Invalid UTF-8");
    if (count >= 3) {
        unsigned char c = data[i+2];
        if (c < 0x80 || c > 0xbf) sh_owned_fail("Invalid UTF-8");
        if (a == 0xe0 && b < 0xa0) sh_owned_fail("Invalid UTF-8");
        if (a == 0xed && b > 0x9f) sh_owned_fail("Invalid UTF-8");
    }
    if (count == 4) {
        unsigned char d = data[i+3];
        if (d < 0x80 || d > 0xbf) sh_owned_fail("Invalid UTF-8");
        if (a == 0xf0 && b < 0x90) sh_owned_fail("Invalid UTF-8");
        if (a == 0xf4 && b > 0x8f) sh_owned_fail("Invalid UTF-8");
    }
    return count;
}

static void sh_validate_utf8(const unsigned char *data, size_t size) {
    for (size_t i = 0; i < size;) i += sh_utf8_step(data, size, i);
}

static sh_owned sh_alloc_copy(const unsigned char *left, size_t l,
                               const unsigned char *right, size_t r) {
    if (l > SIZE_MAX - r) sh_owned_fail("String size overflow");
    size_t size = l + r;
    if (!size) return sh_empty();
    if (size > SH_OWNED_MAX_LIVE_BYTES - sh_live_bytes)
        sh_owned_fail("Live String byte budget exceeded");
    if (size > SIZE_MAX - sizeof(struct sh_owned_buffer))
        sh_owned_fail("String allocation overflow");
    struct sh_owned_buffer *buffer = malloc(sizeof(*buffer) + size);
    if (!buffer) sh_owned_fail("String allocation failed");
    buffer->refs = 1;
    buffer->bytes = size;
    if (l) memcpy(buffer->data, left, l);
    if (r) memcpy(buffer->data + l, right, r);
    sh_live_bytes += size;
    sh_live_objects++;
    return (sh_owned){buffer, 0, size};
}

sh_owned sh_owned_new_utf8(const unsigned char *data, size_t size) {
    if (size && !data) sh_owned_fail("Null input for nonempty String");
    if (size) sh_validate_utf8(data, size);
    return sh_alloc_copy(data, size, NULL, 0);
}

sh_owned sh_owned_retain(sh_owned value) {
    if (value.owner) {
        if (value.owner->refs == SIZE_MAX)
            sh_owned_fail("String reference count overflow");
        value.owner->refs++;
    }
    return value;
}

void sh_owned_drop(sh_owned *value) {
    if (!value) sh_owned_fail("Null String handle");
    struct sh_owned_buffer *buffer = value->owner;
    *value = sh_empty();
    if (!buffer) return;
    if (--buffer->refs == 0) {
        sh_live_bytes -= buffer->bytes;
        sh_live_objects--;
        free(buffer);
    }
}

void sh_owned_copy_assign(sh_owned *destination, sh_owned source) {
    if (!destination) sh_owned_fail("Null String destination");
    /* Retain first: source may refer to the destination's last owner. */
    sh_owned held = sh_owned_retain(source);
    sh_owned_drop(destination);
    *destination = held;
}

void sh_owned_move_assign(sh_owned *destination, sh_owned *source) {
    if (!destination) sh_owned_fail("Null String destination");
    if (!source) sh_owned_fail("Null String move source");
    if (destination == source) return;
    /* Move ownership without incrementing the source's reference count.
     * Clearing source first prevents accidental double-drop by a caller.
     */
    sh_owned moved = *source;
    *source = sh_empty();
    sh_owned_drop(destination);
    *destination = moved;
}

sh_owned sh_owned_concat(sh_owned left, sh_owned right) {
    if (!left.size) return sh_owned_retain(right);
    if (!right.size) return sh_owned_retain(left);
    return sh_alloc_copy(sh_data(left), left.size, sh_data(right), right.size);
}

size_t sh_owned_len_cp(sh_owned value) {
    const unsigned char *data = sh_data(value);
    size_t count = 0;
    for (size_t i = 0; i < value.size;) {
        i += sh_utf8_step(data, value.size, i);
        count++;
    }
    return count;
}

sh_owned sh_owned_slice_cp(sh_owned value, size_t start, size_t end) {
    if (start > end) sh_owned_fail("String slice bounds");
    const unsigned char *data = sh_data(value);
    size_t i = 0, cp = 0, byte_start = 0;
    while (cp < end && i < value.size) {
        if (cp == start) byte_start = i;
        i += sh_utf8_step(data, value.size, i);
        cp++;
    }
    if (cp != end) sh_owned_fail("String slice bounds");
    if (start == end) return sh_empty();
    sh_owned result = sh_owned_retain(value);
    result.offset += byte_start;
    result.size = i - byte_start;
    return result;
}

sh_owned sh_owned_index_cp(sh_owned value, size_t index) {
    if (index == SIZE_MAX) sh_owned_fail("String slice bounds");
    return sh_owned_slice_cp(value, index, index + 1);
}

int sh_owned_equal(sh_owned left, sh_owned right) {
    return left.size == right.size &&
        (left.size == 0 || memcmp(sh_data(left), sh_data(right), left.size) == 0);
}

void sh_owned_print(sh_owned value) {
    if (value.size && fwrite(sh_data(value), 1, value.size, stdout) != value.size)
        sh_owned_fail("String output failed");
    if (putchar('\n') == EOF) sh_owned_fail("String output failed");
}

size_t sh_owned_live_bytes(void) { return sh_live_bytes; }
size_t sh_owned_live_objects(void) { return sh_live_objects; }
