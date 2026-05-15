use vstd::prelude::*;
use std::collections;

fn main() {}

verus! {

// #[derive(Copy, Clone)]
#[derive(PartialEq, Eq, Hash)]
pub struct EndPoint {
    pub id: Vec<u8>,
}

impl EndPoint {

    pub open spec fn view(self) -> AbstractEndPoint {
        AbstractEndPoint{id: self.id@}
    }

}

pub struct AbstractEndPoint {
    pub id: Seq<u8>,
}

impl AbstractEndPoint{

    pub open spec fn valid_physical_address(self) -> bool {
        self.id.len() < 0x100000
    }

    pub open spec fn abstractable(self) -> bool {
        self.valid_physical_address()
    }
}

#[verifier(external_body)]
#[verifier::accept_recursive_types(V)]
pub struct HashMap<V> {
  m: collections::HashMap<EndPoint, V>,
}

impl<V> HashMap<V>
{
    pub uninterp spec fn view(self) -> Map<AbstractEndPoint, V>;

	#[verifier::external_body]
    pub fn insert(&mut self, key: &EndPoint, value: V)
      ensures self@ == old(self)@.insert(key@, value)
	{
		unimplemented!()
	}
}

pub type TombstoneTable = Map<AbstractEndPoint, nat>;

pub struct CTombstoneTable {
    pub epmap: HashMap<u64>,
}

impl CTombstoneTable {

    pub open spec fn abstractable(&self) -> bool {
        forall |k: AbstractEndPoint| #[trigger] self@.contains_key(k) ==> k.valid_physical_address()
    }

    pub open spec fn view(&self) -> TombstoneTable {
        self.epmap@.map_values(|v: u64| v as nat)
    }

    pub fn insert(&mut self, src: &EndPoint, last_seqno: u64)
    requires
        old(self).abstractable(),
        src@.valid_physical_address(),
    ensures
        self@ =~= old(self)@.insert(src@, last_seqno as nat),
        self.abstractable(),
    {
        self.epmap.insert(src, last_seqno);
        assert( forall |k: AbstractEndPoint| #[trigger] self@.contains_key(k) ==> old(self)@.contains_key(k) || k == src@ );
    }
}


// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_insert_equal<V>(r1: (), r2: (), post1_self_: HashMap<V>, post2_self_: HashMap<V>) -> bool {
    (r1 == r2)
    && (post1_self_ == post2_self_)
}

proof fn det_insert<V>(g_neq_tuple: bool, pre_self_: HashMap<V>, key: EndPoint, value: V, post1_self_: HashMap<V>, r1: (), post2_self_: HashMap<V>, r2: ())
    ensures
        ({
            &&& (post1_self_@ == pre_self_@.insert(key@, value))
            &&& (post2_self_@ == pre_self_@.insert(key@, value))
        }) ==> det_insert_equal(r1, r2, post1_self_, post2_self_),
{
    if g_neq_tuple { assume(!det_insert_equal(r1, r2, post1_self_, post2_self_)); }
}
// === END INJECTED ===

}
