/* Samhus research-only owned String runtime (C11).
 * Not linked into the language compiler. No approved ABI/ownership policy.
 * API consumers MUST use sh_owned_retain for copying handles and
 * sh_owned_drop exactly once for every retained handle.
 * Do not shallow-copy handles or share them across threads.
 */
#ifndef SAMHUS_EXPERIMENTAL_OWNED_STRING_H
#define SAMHUS_EXPERIMENTAL_OWNED_STRING_H
#include <stddef.h>
#include <stdio.h>

#define SH_OWNED_MAX_LIVE_BYTES ((size_t)1048576)

typedef struct sh_owned_buffer sh_owned_buffer;
typedef struct {
    sh_owned_buffer *owner;
    size_t offset;
    size_t size;
} sh_owned;

sh_owned sh_owned_new_utf8(const unsigned char *data, size_t size);
sh_owned sh_owned_retain(sh_owned value);
void sh_owned_drop(sh_owned *value);
sh_owned sh_owned_concat(sh_owned left, sh_owned right);
sh_owned sh_owned_slice_cp(sh_owned value, size_t start, size_t end);
sh_owned sh_owned_index_cp(sh_owned value, size_t index);
size_t sh_owned_len_cp(sh_owned value);
int sh_owned_equal(sh_owned left, sh_owned right);
void sh_owned_print(sh_owned value);
size_t sh_owned_live_bytes(void);
size_t sh_owned_live_objects(void);

#endif
