// === set() ===
// Input: (pre: Bitmap, index: usize)
// Output: (post: Bitmap, result: Result<(), Error>)

// R0: Full determinism
proof fn det_set_r0(pre: Bitmap, index: usize, post1: Bitmap, post2: Bitmap, r1: Result<(), Error>, r2: Result<(), Error>)
    requires pre.inv(),
    ensures
        (post1.inv() && (match r1 { Ok(()) => { &&& index<post1@.num_bits &&& post1@.is_bit_set(index as int) &&& !pre@.is_bit_set(index as int) &&& post1@.num_bits==pre@.num_bits &&& forall|i:int| 0<=i<post1@.num_bits && i!=(index as int) ==> post1@.is_bit_set(i)==pre@.is_bit_set(i) &&& post1@.set_bits==pre@.set_bits.insert(index as int) &&& post1@.usage()==pre@.usage()+1 }, Err(_) => { &&& (index>=pre@.num_bits || pre@.is_bit_set(index as int)) &&& post1@==pre@ } })
        && post2.inv() && (match r2 { Ok(()) => { &&& index<post2@.num_bits &&& post2@.is_bit_set(index as int) &&& !pre@.is_bit_set(index as int) &&& post2@.num_bits==pre@.num_bits &&& forall|i:int| 0<=i<post2@.num_bits && i!=(index as int) ==> post2@.is_bit_set(i)==pre@.is_bit_set(i) &&& post2@.set_bits==pre@.set_bits.insert(index as int) &&& post2@.usage()==pre@.usage()+1 }, Err(_) => { &&& (index>=pre@.num_bits || pre@.is_bit_set(index as int)) &&& post2@==pre@ } }))
        ==> (r1==r2 && post1@==post2@)
{ }

// R1: Phase 1 — narrow input. num_bits==8
proof fn det_set_r1(pre: Bitmap, index: usize, post1: Bitmap, post2: Bitmap, r1: Result<(), Error>, r2: Result<(), Error>)
    requires pre.inv(),
    ensures
        (post1.inv() && (match r1 { Ok(()) => { &&& index<post1@.num_bits &&& post1@.is_bit_set(index as int) &&& !pre@.is_bit_set(index as int) &&& post1@.num_bits==pre@.num_bits &&& forall|i:int| 0<=i<post1@.num_bits && i!=(index as int) ==> post1@.is_bit_set(i)==pre@.is_bit_set(i) &&& post1@.set_bits==pre@.set_bits.insert(index as int) &&& post1@.usage()==pre@.usage()+1 }, Err(_) => { &&& (index>=pre@.num_bits || pre@.is_bit_set(index as int)) &&& post1@==pre@ } })
        && post2.inv() && (match r2 { Ok(()) => { &&& index<post2@.num_bits &&& post2@.is_bit_set(index as int) &&& !pre@.is_bit_set(index as int) &&& post2@.num_bits==pre@.num_bits &&& forall|i:int| 0<=i<post2@.num_bits && i!=(index as int) ==> post2@.is_bit_set(i)==pre@.is_bit_set(i) &&& post2@.set_bits==pre@.set_bits.insert(index as int) &&& post2@.usage()==pre@.usage()+1 }, Err(_) => { &&& (index>=pre@.num_bits || pre@.is_bit_set(index as int)) &&& post2@==pre@ } })
        && pre@.num_bits == 8)
        ==> (r1==r2 && post1@==post2@)
{ }

// R2: Phase 1 — narrow input. num_bits==8, index==10 (OOB)
proof fn det_set_r2(pre: Bitmap, index: usize, post1: Bitmap, post2: Bitmap, r1: Result<(), Error>, r2: Result<(), Error>)
    requires pre.inv(),
    ensures
        (post1.inv() && (match r1 { Ok(()) => { &&& index<post1@.num_bits &&& post1@.is_bit_set(index as int) &&& !pre@.is_bit_set(index as int) &&& post1@.num_bits==pre@.num_bits &&& forall|i:int| 0<=i<post1@.num_bits && i!=(index as int) ==> post1@.is_bit_set(i)==pre@.is_bit_set(i) &&& post1@.set_bits==pre@.set_bits.insert(index as int) &&& post1@.usage()==pre@.usage()+1 }, Err(_) => { &&& (index>=pre@.num_bits || pre@.is_bit_set(index as int)) &&& post1@==pre@ } })
        && post2.inv() && (match r2 { Ok(()) => { &&& index<post2@.num_bits &&& post2@.is_bit_set(index as int) &&& !pre@.is_bit_set(index as int) &&& post2@.num_bits==pre@.num_bits &&& forall|i:int| 0<=i<post2@.num_bits && i!=(index as int) ==> post2@.is_bit_set(i)==pre@.is_bit_set(i) &&& post2@.set_bits==pre@.set_bits.insert(index as int) &&& post2@.usage()==pre@.usage()+1 }, Err(_) => { &&& (index>=pre@.num_bits || pre@.is_bit_set(index as int)) &&& post2@==pre@ } })
        && pre@.num_bits == 8 && index == 10)
        ==> (r1==r2 && post1@==post2@)
{ }

// R3: Phase 2 — narrow output. Input: 8-bit, index==10. Both Err, different codes
proof fn det_set_r3(pre: Bitmap, index: usize, post1: Bitmap, post2: Bitmap, r1: Result<(), Error>, r2: Result<(), Error>)
    requires pre.inv(),
    ensures
        (post1.inv() && (match r1 { Ok(()) => { &&& index<post1@.num_bits &&& post1@.is_bit_set(index as int) &&& !pre@.is_bit_set(index as int) &&& post1@.num_bits==pre@.num_bits &&& forall|i:int| 0<=i<post1@.num_bits && i!=(index as int) ==> post1@.is_bit_set(i)==pre@.is_bit_set(i) &&& post1@.set_bits==pre@.set_bits.insert(index as int) &&& post1@.usage()==pre@.usage()+1 }, Err(_) => { &&& (index>=pre@.num_bits || pre@.is_bit_set(index as int)) &&& post1@==pre@ } })
        && post2.inv() && (match r2 { Ok(()) => { &&& index<post2@.num_bits &&& post2@.is_bit_set(index as int) &&& !pre@.is_bit_set(index as int) &&& post2@.num_bits==pre@.num_bits &&& forall|i:int| 0<=i<post2@.num_bits && i!=(index as int) ==> post2@.is_bit_set(i)==pre@.is_bit_set(i) &&& post2@.set_bits==pre@.set_bits.insert(index as int) &&& post2@.usage()==pre@.usage()+1 }, Err(_) => { &&& (index>=pre@.num_bits || pre@.is_bit_set(index as int)) &&& post2@==pre@ } })
        && pre@.num_bits == 8 && index == 10
        && r1 is Err && r2 is Err
        && r1->Err_0.code == ::sys::error::ErrorCode::InvalidArgument
        && r2->Err_0.code == ::sys::error::ErrorCode::ResourceBusy)
        ==> false
{ }
