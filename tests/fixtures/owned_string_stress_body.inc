
/* Fixed-seed 50,000 operations: API-conforming handles only. */
sh_owned slots[12] = {0};
unsigned int random_state = 0x12345678u;
static const unsigned char sample_a[] = "A";
static const unsigned char sample_globe[] = "🌍";
static const unsigned char sample_rocket[] = "🚀";
for (size_t step = 0; step < 50000; ++step) {
    random_state = random_state * 1664525u + 1013904223u;
    const size_t dst = (size_t)(random_state % 12u);
    random_state = random_state * 1664525u + 1013904223u;
    const size_t src = (size_t)(random_state % 12u);
    const unsigned int kind = (random_state >> 11) % 7u;
    if (kind == 0u) {
        sh_owned value = sh_owned_new_utf8(sample_a, sizeof(sample_a) - 1);
        sh_owned_move_assign(&slots[dst], &value);
    } else if (kind == 1u) {
        sh_owned value = sh_owned_new_utf8(
            sample_globe, sizeof(sample_globe) - 1);
        sh_owned_move_assign(&slots[dst], &value);
    } else if (kind == 2u) {
        sh_owned value = sh_owned_new_utf8(
            sample_rocket, sizeof(sample_rocket) - 1);
        sh_owned_move_assign(&slots[dst], &value);
    } else if (kind == 3u) {
        sh_owned_copy_assign(&slots[dst], slots[src]);
    } else if (kind == 4u) {
        sh_owned_move_assign(&slots[dst], &slots[src]);
    } else if (kind == 5u) {
        const size_t count = sh_owned_len_cp(slots[src]);
        if (count) {
            const size_t begin = (size_t)(random_state % (unsigned int)count);
            sh_owned slice = sh_owned_index_cp(slots[src], begin);
            sh_owned_move_assign(&slots[dst], &slice);
        } else {
            sh_owned_copy_assign(&slots[dst], slots[src]);
        }
    } else {
        const size_t total = slots[dst].size + slots[src].size;
        if (total < 256u) {
            sh_owned joined = sh_owned_concat(slots[dst], slots[src]);
            sh_owned_move_assign(&slots[dst], &joined);
        } else {
            sh_owned_copy_assign(&slots[dst], slots[src]);
        }
    }
    if (sh_owned_live_bytes() > SH_OWNED_MAX_LIVE_BYTES)
        return 8;
    if (sh_owned_live_objects() > 12u)
        return 9;
}
for (size_t i = 0; i < 12; ++i) sh_owned_drop(&slots[i]);
printf("%zu %zu\n", sh_owned_live_bytes(), sh_owned_live_objects());
