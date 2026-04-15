// === alloc() ===
// Input: (pre: Bitmap)
// Output: (post: Bitmap, result: Result<usize, Error>)

// R0: Full determinism
proof fn det_alloc_r0(pre: Bitmap, post1: Bitmap, post2: Bitmap, r1: Result<usize, Error>, r2: Result<usize, Error>)
    requires pre.inv(),
    ensures
        (post1.inv() && (match r1 { Ok(i) => { &&& 0<=i<post1@.num_bits &&& post1@.num_bits==pre@.num_bits &&& !pre@.is_bit_set(i as int) &&& post1@.is_bit_set(i as int) &&& forall|j:int| 0<=j<post1@.num_bits && j!=i ==> post1@.is_bit_set(j)==pre@.is_bit_set(j) &&& post1@.set_bits==pre@.set_bits.insert(i as int) &&& post1@.usage()==pre@.usage()+1 }, Err(_) => { &&& pre@.is_full() &&& post1@==pre@ } })
        && post2.inv() && (match r2 { Ok(i) => { &&& 0<=i<post2@.num_bits &&& post2@.num_bits==pre@.num_bits &&& !pre@.is_bit_set(i as int) &&& post2@.is_bit_set(i as int) &&& forall|j:int| 0<=j<post2@.num_bits && j!=i ==> post2@.is_bit_set(j)==pre@.is_bit_set(j) &&& post2@.set_bits==pre@.set_bits.insert(i as int) &&& post2@.usage()==pre@.usage()+1 }, Err(_) => { &&& pre@.is_full() &&& post2@==pre@ } }))
        ==> (r1==r2 && post1@==post2@)
{ }

// R1: Phase 1 — narrow input. pre@.num_bits < 100
proof fn det_alloc_r1(pre: Bitmap, post1: Bitmap, post2: Bitmap, r1: Result<usize, Error>, r2: Result<usize, Error>)
    requires pre.inv(),
    ensures
        (post1.inv() && (match r1 { Ok(i) => { &&& 0<=i<post1@.num_bits &&& post1@.num_bits==pre@.num_bits &&& !pre@.is_bit_set(i as int) &&& post1@.is_bit_set(i as int) &&& forall|j:int| 0<=j<post1@.num_bits && j!=i ==> post1@.is_bit_set(j)==pre@.is_bit_set(j) &&& post1@.set_bits==pre@.set_bits.insert(i as int) &&& post1@.usage()==pre@.usage()+1 }, Err(_) => { &&& pre@.is_full() &&& post1@==pre@ } })
        && post2.inv() && (match r2 { Ok(i) => { &&& 0<=i<post2@.num_bits &&& post2@.num_bits==pre@.num_bits &&& !pre@.is_bit_set(i as int) &&& post2@.is_bit_set(i as int) &&& forall|j:int| 0<=j<post2@.num_bits && j!=i ==> post2@.is_bit_set(j)==pre@.is_bit_set(j) &&& post2@.set_bits==pre@.set_bits.insert(i as int) &&& post2@.usage()==pre@.usage()+1 }, Err(_) => { &&& pre@.is_full() &&& post2@==pre@ } })
        && pre@.num_bits == 8)
        ==> (r1==r2 && post1@==post2@)
{ }

// R2: Phase 1 — narrow input. num_bits==8, usage==0 (empty)
proof fn det_alloc_r2(pre: Bitmap, post1: Bitmap, post2: Bitmap, r1: Result<usize, Error>, r2: Result<usize, Error>)
    requires pre.inv(),
    ensures
        (post1.inv() && (match r1 { Ok(i) => { &&& 0<=i<post1@.num_bits &&& post1@.num_bits==pre@.num_bits &&& !pre@.is_bit_set(i as int) &&& post1@.is_bit_set(i as int) &&& forall|j:int| 0<=j<post1@.num_bits && j!=i ==> post1@.is_bit_set(j)==pre@.is_bit_set(j) &&& post1@.set_bits==pre@.set_bits.insert(i as int) &&& post1@.usage()==pre@.usage()+1 }, Err(_) => { &&& pre@.is_full() &&& post1@==pre@ } })
        && post2.inv() && (match r2 { Ok(i) => { &&& 0<=i<post2@.num_bits &&& post2@.num_bits==pre@.num_bits &&& !pre@.is_bit_set(i as int) &&& post2@.is_bit_set(i as int) &&& forall|j:int| 0<=j<post2@.num_bits && j!=i ==> post2@.is_bit_set(j)==pre@.is_bit_set(j) &&& post2@.set_bits==pre@.set_bits.insert(i as int) &&& post2@.usage()==pre@.usage()+1 }, Err(_) => { &&& pre@.is_full() &&& post2@==pre@ } })
        && pre@.num_bits == 8 && pre@.usage() == 0)
        ==> (r1==r2 && post1@==post2@)
{ }

// R3: Phase 2 — narrow output. Input: 8-bit empty. Both Ok, different index
proof fn det_alloc_r3(pre: Bitmap, post1: Bitmap, post2: Bitmap, r1: Result<usize, Error>, r2: Result<usize, Error>)
    requires pre.inv(),
    ensures
        (post1.inv() && (match r1 { Ok(i) => { &&& 0<=i<post1@.num_bits &&& post1@.num_bits==pre@.num_bits &&& !pre@.is_bit_set(i as int) &&& post1@.is_bit_set(i as int) &&& forall|j:int| 0<=j<post1@.num_bits && j!=i ==> post1@.is_bit_set(j)==pre@.is_bit_set(j) &&& post1@.set_bits==pre@.set_bits.insert(i as int) &&& post1@.usage()==pre@.usage()+1 }, Err(_) => { &&& pre@.is_full() &&& post1@==pre@ } })
        && post2.inv() && (match r2 { Ok(i) => { &&& 0<=i<post2@.num_bits &&& post2@.num_bits==pre@.num_bits &&& !pre@.is_bit_set(i as int) &&& post2@.is_bit_set(i as int) &&& forall|j:int| 0<=j<post2@.num_bits && j!=i ==> post2@.is_bit_set(j)==pre@.is_bit_set(j) &&& post2@.set_bits==pre@.set_bits.insert(i as int) &&& post2@.usage()==pre@.usage()+1 }, Err(_) => { &&& pre@.is_full() &&& post2@==pre@ } })
        && pre@.num_bits == 8 && pre@.usage() == 0
        && r1 is Ok && r2 is Ok
        && r1 == Ok::<usize, Error>(0usize) && r2 == Ok::<usize, Error>(1usize))
        ==> false
{ }
