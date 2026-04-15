// === new() ===
// Input: number_of_bits
// Output: result (Result<Bitmap, Error>)

// R0: Full determinism check
proof fn det_new_r0(nb: usize, r1: Result<Bitmap, Error>, r2: Result<Bitmap, Error>)
    ensures
        ((r1 matches Ok(b1) ==> { &&& b1.inv() &&& b1@.num_bits == nb as int &&& b1@.is_empty() })
        && (nb == 0 ==> r1 is Err) && (nb >= u32::MAX ==> r1 is Err) && (nb % (u8::BITS as usize) != 0 ==> r1 is Err)
        && (r2 matches Ok(b2) ==> { &&& b2.inv() &&& b2@.num_bits == nb as int &&& b2@.is_empty() })
        && (nb == 0 ==> r2 is Err) && (nb >= u32::MAX ==> r2 is Err) && (nb % (u8::BITS as usize) != 0 ==> r2 is Err))
        ==> r1 == r2
{ }

// R1: Phase 1 — narrow input. Is small nb enough?
// Assumes: nb < 100
proof fn det_new_r1(nb: usize, r1: Result<Bitmap, Error>, r2: Result<Bitmap, Error>)
    ensures
        ((r1 matches Ok(b1) ==> { &&& b1.inv() &&& b1@.num_bits == nb as int &&& b1@.is_empty() })
        && (nb == 0 ==> r1 is Err) && (nb >= u32::MAX ==> r1 is Err) && (nb % (u8::BITS as usize) != 0 ==> r1 is Err)
        && (r2 matches Ok(b2) ==> { &&& b2.inv() &&& b2@.num_bits == nb as int &&& b2@.is_empty() })
        && (nb == 0 ==> r2 is Err) && (nb >= u32::MAX ==> r2 is Err) && (nb % (u8::BITS as usize) != 0 ==> r2 is Err)
        && nb < 100)
        ==> r1 == r2
{ }

// R2: Phase 1 — narrow further. nb == 8?
// Assumes: nb == 8
proof fn det_new_r2(nb: usize, r1: Result<Bitmap, Error>, r2: Result<Bitmap, Error>)
    ensures
        ((r1 matches Ok(b1) ==> { &&& b1.inv() &&& b1@.num_bits == nb as int &&& b1@.is_empty() })
        && (nb == 0 ==> r1 is Err) && (nb >= u32::MAX ==> r1 is Err) && (nb % (u8::BITS as usize) != 0 ==> r1 is Err)
        && (r2 matches Ok(b2) ==> { &&& b2.inv() &&& b2@.num_bits == nb as int &&& b2@.is_empty() })
        && (nb == 0 ==> r2 is Err) && (nb >= u32::MAX ==> r2 is Err) && (nb % (u8::BITS as usize) != 0 ==> r2 is Err)
        && nb == 8)
        ==> r1 == r2
{ }

// R3: Phase 1 — control. nb == 0?
// Assumes: nb == 0
proof fn det_new_r3(nb: usize, r1: Result<Bitmap, Error>, r2: Result<Bitmap, Error>)
    ensures
        ((r1 matches Ok(b1) ==> { &&& b1.inv() &&& b1@.num_bits == nb as int &&& b1@.is_empty() })
        && (nb == 0 ==> r1 is Err) && (nb >= u32::MAX ==> r1 is Err) && (nb % (u8::BITS as usize) != 0 ==> r1 is Err)
        && (r2 matches Ok(b2) ==> { &&& b2.inv() &&& b2@.num_bits == nb as int &&& b2@.is_empty() })
        && (nb == 0 ==> r2 is Err) && (nb >= u32::MAX ==> r2 is Err) && (nb % (u8::BITS as usize) != 0 ==> r2 is Err)
        && nb == 0)
        ==> r1 == r2
{ }

// R4: Phase 2 — narrow output. Input fixed at nb=8. Which variant combo?
// Assumes: nb == 8, r1 is Ok, r2 is Err
proof fn det_new_r4(nb: usize, r1: Result<Bitmap, Error>, r2: Result<Bitmap, Error>)
    ensures
        ((r1 matches Ok(b1) ==> { &&& b1.inv() &&& b1@.num_bits == nb as int &&& b1@.is_empty() })
        && (nb == 0 ==> r1 is Err) && (nb >= u32::MAX ==> r1 is Err) && (nb % (u8::BITS as usize) != 0 ==> r1 is Err)
        && (r2 matches Ok(b2) ==> { &&& b2.inv() &&& b2@.num_bits == nb as int &&& b2@.is_empty() })
        && (nb == 0 ==> r2 is Err) && (nb >= u32::MAX ==> r2 is Err) && (nb % (u8::BITS as usize) != 0 ==> r2 is Err)
        && nb == 8
        && r1 is Ok
        && r2 is Err)
        ==> false
{ }
