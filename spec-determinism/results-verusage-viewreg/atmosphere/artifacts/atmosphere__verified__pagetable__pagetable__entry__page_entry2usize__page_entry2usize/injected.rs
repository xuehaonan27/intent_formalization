use vstd::prelude::*;
use vstd::simple_pptr::*;

fn main() {}

verus!{

global size_of usize==8;

pub type PAddr = usize;

// File: pagetable/entry.rs
#[derive(Clone,Debug)]
pub struct PageEntryPerm {
    pub present: bool,
    pub ps: bool,
    pub write: bool,
    pub execute_disable: bool,
    pub user: bool,
}

#[derive(Clone,Debug)]
pub struct PageEntry {
    pub addr: PAddr,
    pub perm: PageEntryPerm,
    // pub ps: bool,
}

pub open spec fn usize2present(v: usize) -> bool {
    (v & PAGE_ENTRY_PRESENT_MASK as usize) != 0
}

pub open spec fn usize2ps(v: usize) -> bool {
    (v & PAGE_ENTRY_PS_MASK as usize) != 0
}

pub open spec fn usize2write(v: usize) -> bool {
    (v & PAGE_ENTRY_WRITE_MASK as usize) != 0
}

pub open spec fn usize2execute_disable(v: usize) -> bool {
    (v & PAGE_ENTRY_EXECUTE_MASK as usize) != 0
}

pub open spec fn usize2user(v: usize) -> bool {
    (v & PAGE_ENTRY_USER_MASK as usize) != 0
}

pub open spec fn spec_usize2page_entry_perm(v: usize) -> PageEntryPerm {
    PageEntryPerm {
        present: usize2present(v),
        ps: usize2ps(v),
        write: usize2write(v),
        execute_disable: usize2execute_disable(v),
        user: usize2user(v),
    }
}

#[verifier::external_body]
#[verifier(when_used_as_spec(spec_usize2page_entry_perm))]
pub fn usize2page_entry_perm(v: usize) -> (ret: PageEntryPerm)
    ensures
        ret =~= spec_usize2page_entry_perm(v),
        v == 0 ==> ret.present == false && ret.ps == false && ret.write == false
            && ret.execute_disable == false && ret.user == false,
{
    unimplemented!()
}

pub open spec fn spec_usize2pa(v: usize) -> PAddr {
    v & MEM_MASK as usize
}

pub fn page_entry2usize(page_entry: &PageEntry) -> (ret: usize)
    requires
        MEM_valid(page_entry.addr),
    ensures
        usize2present(ret) == page_entry.perm.present,
        usize2ps(ret) == page_entry.perm.ps,
        usize2write(ret) == page_entry.perm.write,
        usize2execute_disable(ret) == page_entry.perm.execute_disable,
        usize2user(ret) == page_entry.perm.user,
        usize2pa(ret) == page_entry.addr,
        usize2page_entry_perm(ret) =~= page_entry.perm,
{
    let mut ret: usize = page_entry.addr;

    let mut ghost_addr = Ghost(page_entry.addr);
    let mut ghost_ret = Ghost(page_entry.addr);
    let ghost_present = Ghost(page_entry.perm.present);
    let ghost_ps = Ghost(page_entry.perm.ps);
    let ghost_write = Ghost(page_entry.perm.write);
    let ghost_execute_disable = Ghost(page_entry.perm.execute_disable);
    let ghost_user = Ghost(page_entry.perm.user);
    assert(ret == ghost_addr@);

    if page_entry.perm.present == true {
        assert(((ret | 0x1u64 as usize) & 0x1u64 as usize) != 0) by (bit_vector);
        assert(((ret | 0x1u64 as usize) & 0x0000_ffff_ffff_f000u64 as usize) == ghost_addr@)
            by (bit_vector)
            requires
                ghost_addr@ & (!0x0000_ffff_ffff_f000u64) as usize == 0 && ghost_addr@ == ret,
        ;

        ret = ret | 0x1u64 as usize;

        assert((ret & 0x1u64 as usize) != 0);
        assert(usize2present(ret) == page_entry.perm.present);
        assert((ret & 0x0000_ffff_ffff_f000u64 as usize) == page_entry.addr);
        assert(usize2pa(ret) == page_entry.addr);

        assert((ghost_ret@ | 0x1u64 as usize) & (!(0x1u64 | 0x0000_ffff_ffff_f000u64)) as usize
            == 0) by (bit_vector)
            requires
                ghost_ret@ & (!0x0000_ffff_ffff_f000u64) as usize == 0,
        ;
        assert(ret & (!(PAGE_ENTRY_PRESENT_MASK | MEM_MASK)) as usize == 0);
    } else {
        assert((ret & 0x1u64 as usize) == 0) by (bit_vector)
            requires
                ret & (!0x0000_ffff_ffff_f000u64) as usize == 0,
        ;
        assert(usize2present(ret) == page_entry.perm.present);

        assert((ret & 0x0000_ffff_ffff_f000u64 as usize) == ret) by (bit_vector)
            requires
                ret & (!0x0000_ffff_ffff_f000u64) as usize == 0,
        ;
        assert(usize2pa(ret) == page_entry.addr);

        assert(ghost_addr@ & (!(0x1u64 | 0x0000_ffff_ffff_f000u64)) as usize == 0) by (bit_vector)
            requires
                ghost_addr@ & (!0x0000_ffff_ffff_f000u64) as usize == 0,
        ;
        assert(ret & (!(PAGE_ENTRY_PRESENT_MASK | MEM_MASK)) as usize == 0);
    }

    assert(usize2present(ret) == page_entry.perm.present);
    assert(usize2pa(ret) == page_entry.addr);
    assert(ret & (!(PAGE_ENTRY_PRESENT_MASK | MEM_MASK)) as usize == 0);

    ghost_ret = Ghost(ret);

    if page_entry.perm.ps == true {
        assert(((ret | (0x1u64 << 0x7u64) as usize) & (0x1u64 << 0x7u64) as usize) != 0)
            by (bit_vector);
        assert(((ret | (0x1u64 << 0x7u64) as usize) & 0x1 as usize) != 0 == ghost_present@)
            by (bit_vector)
            requires
                ghost_ret@ == ret && (ret & 0x1u64 as usize) != 0 == ghost_present@,
        ;
        assert(((ret | (0x1u64 << 0x7u64) as usize) & 0x0000_ffff_ffff_f000u64 as usize)
            == ghost_addr@) by (bit_vector)
            requires
                ghost_ret@ == ret && (ghost_ret@ & 0x0000_ffff_ffff_f000u64 as usize)
                    == ghost_addr@,
        ;
        ret = ret | (0x1u64 << 0x7u64) as usize;

        assert((ret & 0x1 as usize) != 0 == ghost_present@);
        assert(usize2present(ret) == page_entry.perm.present);
        assert((ret & (0x1u64 << 0x7u64) as usize) != 0);
        assert(usize2ps(ret) == page_entry.perm.ps);
        assert((ret & 0x0000_ffff_ffff_f000u64 as usize) == ghost_addr@);
        assert(usize2pa(ret) == page_entry.addr);

        assert((ghost_ret@ | (0x1u64 << 0x7u64) as usize) & (!(0x1u64 | 0x1u64 << 0x7u64
            | 0x0000_ffff_ffff_f000u64)) as usize == 0) by (bit_vector)
            requires
                ghost_ret@ & (!(0x1u64 | 0x0000_ffff_ffff_f000u64)) as usize == 0,
        ;
        assert(ret & (!(PAGE_ENTRY_PRESENT_MASK | PAGE_ENTRY_PS_MASK | MEM_MASK)) as usize == 0);
    } else {
        assert((ret & (0x1u64 << 0x7u64) as usize) == 0) by (bit_vector)
            requires
                ret & (!(0x1u64 | 0x0000_ffff_ffff_f000u64)) as usize == 0,
        ;

        assert(usize2present(ret) == page_entry.perm.present);
        assert(usize2ps(ret) == page_entry.perm.ps);
        assert(usize2pa(ret) == page_entry.addr);

        assert(ret & (!(0x1u64 | 0x1u64 << 0x7u64 | 0x0000_ffff_ffff_f000u64)) as usize == 0)
            by (bit_vector)
            requires
                ret & (!(0x1u64 | 0x0000_ffff_ffff_f000u64)) as usize == 0,
        ;
        assert(ret & (!(PAGE_ENTRY_PRESENT_MASK | PAGE_ENTRY_PS_MASK | MEM_MASK)) as usize == 0);
    }

    assert(usize2present(ret) == page_entry.perm.present);
    assert(usize2ps(ret) == page_entry.perm.ps);
    assert(usize2pa(ret) == page_entry.addr);
    assert(ret & (!(PAGE_ENTRY_PRESENT_MASK | PAGE_ENTRY_PS_MASK | MEM_MASK)) as usize == 0);

    ghost_ret = Ghost(ret);

    if page_entry.perm.write == true {
        assert(((ret | (0x1u64 << 0x1u64) as usize) & (0x1u64 << 0x1u64) as usize) != 0)
            by (bit_vector);
        assert(((ret | (0x1u64 << 0x1u64) as usize) & 0x1 as usize) != 0 == ghost_present@)
            by (bit_vector)
            requires
                ghost_ret@ == ret && (ret & 0x1u64 as usize) != 0 == ghost_present@,
        ;
        assert(((ret | (0x1u64 << 0x1u64) as usize) & (0x1u64 << 0x7u64) as usize) != 0
            == ghost_ps@) by (bit_vector)
            requires
                ghost_ret@ == ret && (ret & (0x1u64 << 0x7u64) as usize) != 0 == ghost_ps@,
        ;
        assert(((ret | (0x1u64 << 0x1u64) as usize) & 0x0000_ffff_ffff_f000u64 as usize)
            == ghost_addr@) by (bit_vector)
            requires
                ghost_ret@ == ret && (ghost_ret@ & 0x0000_ffff_ffff_f000u64 as usize)
                    == ghost_addr@,
        ;
        ret = ret | (0x1u64 << 0x1u64) as usize;

        assert((ret & 0x1 as usize) != 0 == ghost_present@);
        assert(usize2present(ret) == page_entry.perm.present);
        assert((ret & (0x1u64 << 0x7u64) as usize) != 0 == ghost_ps@);
        assert(usize2ps(ret) == page_entry.perm.ps);
        assert((ret & (0x1u64 << 0x1u64) as usize) != 0);
        assert(usize2write(ret) == page_entry.perm.write);
        assert((ret & 0x0000_ffff_ffff_f000u64 as usize) == ghost_addr@);
        assert(usize2pa(ret) == page_entry.addr);

        assert((ghost_ret@ | (0x1u64 << 0x1u64) as usize) & (!(0x1u64 | 0x1u64 << 0x7u64 | 0x1u64
            << 0x1u64 | 0x0000_ffff_ffff_f000u64)) as usize == 0) by (bit_vector)
            requires
                ghost_ret@ & (!(0x1u64 | 0x1u64 << 0x7u64 | 0x0000_ffff_ffff_f000u64)) as usize
                    == 0,
        ;
        assert(ret & (!(PAGE_ENTRY_PRESENT_MASK | PAGE_ENTRY_PS_MASK | PAGE_ENTRY_WRITE_MASK
            | MEM_MASK)) as usize == 0);
    } else {
        assert((ret & (0x1u64 << 0x1u64) as usize) == 0) by (bit_vector)
            requires
                ret & (!(0x1u64 | 0x1u64 << 0x7u64 | 0x0000_ffff_ffff_f000u64)) as usize == 0,
        ;

        assert(usize2present(ret) == page_entry.perm.present);
        assert(usize2ps(ret) == page_entry.perm.ps);
        assert(usize2write(ret) == page_entry.perm.write);
        assert(usize2pa(ret) == page_entry.addr);

        assert(ret & (!(0x1u64 | 0x1u64 << 0x7u64 | 0x1u64 << 0x1u64
            | 0x0000_ffff_ffff_f000u64)) as usize == 0) by (bit_vector)
            requires
                ret & (!(0x1u64 | 0x1u64 << 0x7u64 | 0x0000_ffff_ffff_f000u64)) as usize == 0,
        ;
        assert(ret & (!(PAGE_ENTRY_PRESENT_MASK | PAGE_ENTRY_PS_MASK | PAGE_ENTRY_WRITE_MASK
            | MEM_MASK)) as usize == 0);
    }

    assert(usize2present(ret) == page_entry.perm.present);
    assert(usize2ps(ret) == page_entry.perm.ps);
    assert(usize2write(ret) == page_entry.perm.write);
    assert(usize2pa(ret) == page_entry.addr);
    assert(ret & (!(PAGE_ENTRY_PRESENT_MASK | PAGE_ENTRY_PS_MASK | PAGE_ENTRY_WRITE_MASK
        | MEM_MASK)) as usize == 0);

    ghost_ret = Ghost(ret);

    if page_entry.perm.execute_disable == true {
        assert(((ret | (0x1u64 << 63u64) as usize) & (0x1u64 << 63u64) as usize) != 0)
            by (bit_vector);
        assert(((ret | (0x1u64 << 63u64) as usize) & 0x1 as usize) != 0 == ghost_present@)
            by (bit_vector)
            requires
                ghost_ret@ == ret && (ret & 0x1u64 as usize) != 0 == ghost_present@,
        ;
        assert(((ret | (0x1u64 << 63u64) as usize) & (0x1u64 << 0x7u64) as usize) != 0 == ghost_ps@)
            by (bit_vector)
            requires
                ghost_ret@ == ret && (ret & (0x1u64 << 0x7u64) as usize) != 0 == ghost_ps@,
        ;
        assert(((ret | (0x1u64 << 63u64) as usize) & (0x1u64 << 0x1u64) as usize) != 0
            == ghost_write@) by (bit_vector)
            requires
                ghost_ret@ == ret && (ret & (0x1u64 << 0x1u64) as usize) != 0 == ghost_write@,
        ;
        assert(((ret | (0x1u64 << 63u64) as usize) & 0x0000_ffff_ffff_f000u64 as usize)
            == ghost_addr@) by (bit_vector)
            requires
                ghost_ret@ == ret && (ghost_ret@ & 0x0000_ffff_ffff_f000u64 as usize)
                    == ghost_addr@,
        ;
        ret = ret | (0x1u64 << 63u64) as usize;

        assert((ret & 0x1 as usize) != 0 == ghost_present@);
        assert(usize2present(ret) == page_entry.perm.present);
        assert((ret & (0x1u64 << 0x7u64) as usize) != 0 == ghost_ps@);
        assert(usize2ps(ret) == page_entry.perm.ps);
        assert((ret & (0x1u64 << 0x1u64) as usize) != 0 == ghost_write@);
        assert(usize2write(ret) == page_entry.perm.write);
        assert((ret & (0x1u64 << 63u64) as usize) != 0);
        assert(usize2execute_disable(ret) == page_entry.perm.execute_disable);
        assert((ret & 0x0000_ffff_ffff_f000u64 as usize) == ghost_addr@);
        assert(usize2pa(ret) == page_entry.addr);

        assert((ghost_ret@ | (0x1u64 << 63u64) as usize) & (!(0x1u64 | 0x1u64 << 0x7u64 | 0x1u64
            << 0x1u64 | 0x1u64 << 63u64 | 0x0000_ffff_ffff_f000u64)) as usize == 0) by (bit_vector)
            requires
                ghost_ret@ & (!(0x1u64 | 0x1u64 << 0x7u64 | 0x1u64 << 0x1u64
                    | 0x0000_ffff_ffff_f000u64)) as usize == 0,
        ;
        assert(ret & (!(PAGE_ENTRY_PRESENT_MASK | PAGE_ENTRY_PS_MASK | PAGE_ENTRY_WRITE_MASK
            | PAGE_ENTRY_EXECUTE_MASK | MEM_MASK)) as usize == 0);
    } else {
        assert((ret & (0x1u64 << 63u64) as usize) == 0) by (bit_vector)
            requires
                ret & (!(0x1u64 | 0x1u64 << 0x7u64 | 0x1u64 << 0x1u64
                    | 0x0000_ffff_ffff_f000u64)) as usize == 0,
        ;

        assert(usize2present(ret) == page_entry.perm.present);
        assert(usize2ps(ret) == page_entry.perm.ps);
        assert(usize2write(ret) == page_entry.perm.write);
        assert(usize2execute_disable(ret) == page_entry.perm.execute_disable);
        assert(usize2pa(ret) == page_entry.addr);

        assert(ret & (!(0x1u64 | 0x1u64 << 0x7u64 | 0x1u64 << 0x1u64 | 0x1u64 << 63u64
            | 0x0000_ffff_ffff_f000u64)) as usize == 0) by (bit_vector)
            requires
                ret & (!(0x1u64 | 0x1u64 << 0x7u64 | 0x1u64 << 0x1u64
                    | 0x0000_ffff_ffff_f000u64)) as usize == 0,
        ;
        assert(ret & (!(PAGE_ENTRY_PRESENT_MASK | PAGE_ENTRY_PS_MASK | PAGE_ENTRY_WRITE_MASK
            | PAGE_ENTRY_EXECUTE_MASK | MEM_MASK)) as usize == 0);
    }

    assert(usize2present(ret) == page_entry.perm.present);
    assert(usize2ps(ret) == page_entry.perm.ps);
    assert(usize2write(ret) == page_entry.perm.write);
    assert(usize2execute_disable(ret) == page_entry.perm.execute_disable);
    assert(usize2pa(ret) == page_entry.addr);
    assert(ret & (!(PAGE_ENTRY_PRESENT_MASK | PAGE_ENTRY_PS_MASK | PAGE_ENTRY_WRITE_MASK
        | PAGE_ENTRY_EXECUTE_MASK | MEM_MASK)) as usize == 0);

    ghost_ret = Ghost(ret);

    if page_entry.perm.user == true {
        assert(((ret | (0x1u64 << 2u64) as usize) & (0x1u64 << 2u64) as usize) != 0)
            by (bit_vector);
        assert(((ret | (0x1u64 << 2u64) as usize) & 0x1 as usize) != 0 == ghost_present@)
            by (bit_vector)
            requires
                ghost_ret@ == ret && (ret & 0x1u64 as usize) != 0 == ghost_present@,
        ;
        assert(((ret | (0x1u64 << 2u64) as usize) & (0x1u64 << 0x7u64) as usize) != 0 == ghost_ps@)
            by (bit_vector)
            requires
                ghost_ret@ == ret && (ret & (0x1u64 << 0x7u64) as usize) != 0 == ghost_ps@,
        ;
        assert(((ret | (0x1u64 << 2u64) as usize) & (0x1u64 << 0x1u64) as usize) != 0
            == ghost_write@) by (bit_vector)
            requires
                ghost_ret@ == ret && (ret & (0x1u64 << 0x1u64) as usize) != 0 == ghost_write@,
        ;
        assert(((ret | (0x1u64 << 2u64) as usize) & (0x1u64 << 63u64) as usize) != 0
            == ghost_execute_disable@) by (bit_vector)
            requires
                ghost_ret@ == ret && (ret & (0x1u64 << 63u64) as usize) != 0
                    == ghost_execute_disable@,
        ;
        assert(((ret | (0x1u64 << 2u64) as usize) & 0x0000_ffff_ffff_f000u64 as usize)
            == ghost_addr@) by (bit_vector)
            requires
                ghost_ret@ == ret && (ghost_ret@ & 0x0000_ffff_ffff_f000u64 as usize)
                    == ghost_addr@,
        ;
        ret = ret | (0x1u64 << 2u64) as usize;

        assert((ret & 0x1 as usize) != 0 == ghost_present@);
        assert(usize2present(ret) == page_entry.perm.present);
        assert((ret & (0x1u64 << 0x7u64) as usize) != 0 == ghost_ps@);
        assert(usize2ps(ret) == page_entry.perm.ps);
        assert((ret & (0x1u64 << 0x1u64) as usize) != 0 == ghost_write@);
        assert(usize2write(ret) == page_entry.perm.write);
        assert((ret & (0x1u64 << 63u64) as usize) != 0 == ghost_execute_disable@);
        assert(usize2execute_disable(ret) == page_entry.perm.execute_disable);
        assert((ret & (0x1u64 << 2u64) as usize) != 0);
        assert(usize2user(ret) == page_entry.perm.user);
        assert((ret & 0x0000_ffff_ffff_f000u64 as usize) == ghost_addr@);
        assert(usize2pa(ret) == page_entry.addr);

        assert((ghost_ret@ | (0x1u64 << 2u64) as usize) & (!(0x1u64 | 0x1u64 << 0x7u64 | 0x1u64
            << 0x1u64 | 0x1u64 << 63u64 | 0x1u64 << 2u64 | 0x0000_ffff_ffff_f000u64)) as usize == 0)
            by (bit_vector)
            requires
                ghost_ret@ & (!(0x1u64 | 0x1u64 << 0x7u64 | 0x1u64 << 0x1u64 | 0x1u64 << 63u64
                    | 0x0000_ffff_ffff_f000u64)) as usize == 0,
        ;
        assert(ret & (!(PAGE_ENTRY_PRESENT_MASK | PAGE_ENTRY_PS_MASK | PAGE_ENTRY_WRITE_MASK
            | PAGE_ENTRY_EXECUTE_MASK | PAGE_ENTRY_USER_MASK | MEM_MASK)) as usize == 0);
    } else {
        assert((ret & (0x1u64 << 2u64) as usize) == 0) by (bit_vector)
            requires
                ret & (!(0x1u64 | 0x1u64 << 0x7u64 | 0x1u64 << 0x1u64 | 0x1u64 << 63u64
                    | 0x0000_ffff_ffff_f000u64)) as usize == 0,
        ;

        assert(usize2present(ret) == page_entry.perm.present);
        assert(usize2ps(ret) == page_entry.perm.ps);
        assert(usize2write(ret) == page_entry.perm.write);
        assert(usize2execute_disable(ret) == page_entry.perm.execute_disable);
        assert(usize2user(ret) == page_entry.perm.user);
        assert(usize2pa(ret) == page_entry.addr);

        assert(ret & (!(0x1u64 | 0x1u64 << 0x7u64 | 0x1u64 << 0x1u64 | 0x1u64 << 63u64 | 0x1u64
            << 2u64 | 0x0000_ffff_ffff_f000u64)) as usize == 0) by (bit_vector)
            requires
                ret & (!(0x1u64 | 0x1u64 << 0x7u64 | 0x1u64 << 0x1u64 | 0x1u64 << 63u64
                    | 0x0000_ffff_ffff_f000u64)) as usize == 0,
        ;
        assert(ret & (!(PAGE_ENTRY_PRESENT_MASK | PAGE_ENTRY_PS_MASK | PAGE_ENTRY_WRITE_MASK
            | PAGE_ENTRY_EXECUTE_MASK | PAGE_ENTRY_USER_MASK | MEM_MASK)) as usize == 0);
    }

    assert(usize2present(ret) == page_entry.perm.present);
    assert(usize2ps(ret) == page_entry.perm.ps);
    assert(usize2write(ret) == page_entry.perm.write);
    assert(usize2execute_disable(ret) == page_entry.perm.execute_disable);
    assert(usize2user(ret) == page_entry.perm.user);
    assert(usize2pa(ret) == page_entry.addr);

    return ret;
}

#[verifier::external_body]
#[verifier(when_used_as_spec(spec_usize2pa))]
pub fn usize2pa(v: usize) -> (ret: PAddr)
    ensures
        ret =~= spec_usize2pa(v),
        MEM_valid(ret),
{
    unimplemented!()
}



// File: util/page_ptr_util_u.rs
pub open spec fn MEM_valid(v: PAddr) -> bool {
    v & (!MEM_MASK) as usize == 0
}


// File: define.rs
pub const MEM_MASK: u64 = 0x0000_ffff_ffff_f000;

pub const PAGE_ENTRY_WRITE_SHIFT: u64 = 1;

pub const PAGE_ENTRY_USER_SHIFT: u64 = 2;

pub const PAGE_ENTRY_PS_SHIFT: u64 = 7;

pub const PAGE_ENTRY_EXECUTE_SHIFT: u64 = 63;

pub const PAGE_ENTRY_PRESENT_MASK: u64 = 0x1;

pub const PAGE_ENTRY_WRITE_MASK: u64 = 0x1u64 << PAGE_ENTRY_WRITE_SHIFT;

pub const PAGE_ENTRY_USER_MASK: u64 = 0x1u64 << PAGE_ENTRY_USER_SHIFT;

pub const PAGE_ENTRY_PS_MASK: u64 = 0x1u64 << PAGE_ENTRY_PS_SHIFT;

pub const PAGE_ENTRY_EXECUTE_MASK: u64 = 0x1u64 << PAGE_ENTRY_EXECUTE_SHIFT;



// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_page_entry2usize_equal(r1: usize, r2: usize) -> bool {
    (r1 == r2)
}

proof fn det_page_entry2usize(g_page_entry_perm_present_is_true: bool, g_page_entry_perm_present_is_false: bool, g_page_entry_perm_ps_is_true: bool, g_page_entry_perm_ps_is_false: bool, g_page_entry_perm_write_is_true: bool, g_page_entry_perm_write_is_false: bool, g_page_entry_perm_execute_disable_is_true: bool, g_page_entry_perm_execute_disable_is_false: bool, g_page_entry_perm_user_is_true: bool, g_page_entry_perm_user_is_false: bool, g_r1_eq: bool, k_r1_eq: int, g_r1_rng: bool, k_r1_rng_lo: int, k_r1_rng_hi: int, g_r2_eq: bool, k_r2_eq: int, g_r2_rng: bool, k_r2_rng_lo: int, k_r2_rng_hi: int, g_neq_tuple: bool, page_entry: PageEntry, r1: usize, r2: usize)
    requires (MEM_valid(page_entry.addr)),
    ensures
        ({
            &&& (usize2present(r1) == page_entry.perm.present)
            &&& (usize2ps(r1) == page_entry.perm.ps)
            &&& (usize2write(r1) == page_entry.perm.write)
            &&& (usize2execute_disable(r1) == page_entry.perm.execute_disable)
            &&& (usize2user(r1) == page_entry.perm.user)
            &&& (usize2pa(r1) == page_entry.addr)
            &&& (usize2page_entry_perm(r1) =~= page_entry.perm)
            &&& (usize2present(r2) == page_entry.perm.present)
            &&& (usize2ps(r2) == page_entry.perm.ps)
            &&& (usize2write(r2) == page_entry.perm.write)
            &&& (usize2execute_disable(r2) == page_entry.perm.execute_disable)
            &&& (usize2user(r2) == page_entry.perm.user)
            &&& (usize2pa(r2) == page_entry.addr)
            &&& (usize2page_entry_perm(r2) =~= page_entry.perm)
        }) ==> det_page_entry2usize_equal(r1, r2),
{
    if g_page_entry_perm_present_is_true { assume(page_entry.perm.present == true); }
    if g_page_entry_perm_present_is_false { assume(page_entry.perm.present == false); }
    if g_page_entry_perm_ps_is_true { assume(page_entry.perm.ps == true); }
    if g_page_entry_perm_ps_is_false { assume(page_entry.perm.ps == false); }
    if g_page_entry_perm_write_is_true { assume(page_entry.perm.write == true); }
    if g_page_entry_perm_write_is_false { assume(page_entry.perm.write == false); }
    if g_page_entry_perm_execute_disable_is_true { assume(page_entry.perm.execute_disable == true); }
    if g_page_entry_perm_execute_disable_is_false { assume(page_entry.perm.execute_disable == false); }
    if g_page_entry_perm_user_is_true { assume(page_entry.perm.user == true); }
    if g_page_entry_perm_user_is_false { assume(page_entry.perm.user == false); }
    if g_r1_eq { assume(r1 as int == k_r1_eq); }
    if g_r1_rng { assume(r1 as int >= k_r1_rng_lo && r1 as int <= k_r1_rng_hi); }
    if g_r2_eq { assume(r2 as int == k_r2_eq); }
    if g_r2_rng { assume(r2 as int >= k_r2_rng_lo && r2 as int <= k_r2_rng_hi); }
    if g_neq_tuple { assume(!det_page_entry2usize_equal(r1, r2)); }
}
// === END INJECTED ===

}
