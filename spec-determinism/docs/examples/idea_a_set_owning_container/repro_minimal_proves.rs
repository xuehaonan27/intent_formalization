// Real-shape reproducer: equal-fn compares `arr_seq@` element-wise via
// two foralls with disjoint triggers. This is the exact pattern seen in
// atmosphere set_owning_container / set_state / set_value / set_mapping.
use vstd::prelude::*;

fn main() {}

verus! {

pub struct Page {
    pub addr: u64,
    pub state: u8,
    pub is_io_page: bool,
    pub ref_count: usize,
    pub owning_container: Option<u64>,
}

pub const NUM_PAGES: usize = 32;

pub struct Allocator {
    pub page_array_seq: Ghost<Seq<Page>>,
    // (in the real case there are more ghost fields, all pinned to pre.)
}

impl Allocator {
    pub open spec fn page_array(self) -> Seq<Page> { self.page_array_seq@ }
    pub open spec fn wf(self) -> bool { self.page_array_seq@.len() == NUM_PAGES }
}

spec fn det_eq(post1: Allocator, post2: Allocator) -> bool {
    post1.page_array_seq == post2.page_array_seq
}

proof fn det_set_owning_container(
    g_neq: bool,
    pre: Allocator,
    index: usize,
    new_oc: Option<u64>,
    post1: Allocator,
    post2: Allocator,
)
    requires pre.wf(), 0 <= index < NUM_PAGES,
    ensures
        ({
            &&& post1.wf()
            &&& (forall|i: int|
                #![trigger post1.page_array_seq@[i]]
                #![trigger pre.page_array_seq@[i]]
                0 <= i < NUM_PAGES && i != index ==> post1.page_array_seq@[i] =~= pre.page_array_seq@[i])
            &&& post1.page_array_seq@[index as int].addr =~= pre.page_array_seq@[index as int].addr
            &&& post1.page_array_seq@[index as int].state =~= pre.page_array_seq@[index as int].state
            &&& post1.page_array_seq@[index as int].is_io_page =~= pre.page_array_seq@[index as int].is_io_page
            &&& post1.page_array_seq@[index as int].ref_count =~= pre.page_array_seq@[index as int].ref_count
            &&& post1.page_array_seq@[index as int].owning_container =~= new_oc
            &&& post2.wf()
            &&& (forall|i: int|
                #![trigger post2.page_array_seq@[i]]
                #![trigger pre.page_array_seq@[i]]
                0 <= i < NUM_PAGES && i != index ==> post2.page_array_seq@[i] =~= pre.page_array_seq@[i])
            &&& post2.page_array_seq@[index as int].addr =~= pre.page_array_seq@[index as int].addr
            &&& post2.page_array_seq@[index as int].state =~= pre.page_array_seq@[index as int].state
            &&& post2.page_array_seq@[index as int].is_io_page =~= pre.page_array_seq@[index as int].is_io_page
            &&& post2.page_array_seq@[index as int].ref_count =~= pre.page_array_seq@[index as int].ref_count
            &&& post2.page_array_seq@[index as int].owning_container =~= new_oc
        }) ==> det_eq(post1, post2),
{
    if g_neq { assume(!det_eq(post1, post2)); }

    // ====== LLM-INSERTED PROOF ======
    // Bring the ensures-hypothesis H into scope so the body can
    // reason from it. The two foralls have disjoint triggers
    // (post1[i] / post2[i]), so z3 needs us to explicitly align
    // them at each i.
    if post1.wf()
        && (forall|i: int|
            #![trigger post1.page_array_seq@[i]]
            #![trigger pre.page_array_seq@[i]]
            0 <= i < NUM_PAGES && i != index ==> post1.page_array_seq@[i] =~= pre.page_array_seq@[i])
        && post1.page_array_seq@[index as int].addr =~= pre.page_array_seq@[index as int].addr
        && post1.page_array_seq@[index as int].state =~= pre.page_array_seq@[index as int].state
        && post1.page_array_seq@[index as int].is_io_page =~= pre.page_array_seq@[index as int].is_io_page
        && post1.page_array_seq@[index as int].ref_count =~= pre.page_array_seq@[index as int].ref_count
        && post1.page_array_seq@[index as int].owning_container =~= new_oc
        && post2.wf()
        && (forall|i: int|
            #![trigger post2.page_array_seq@[i]]
            #![trigger pre.page_array_seq@[i]]
            0 <= i < NUM_PAGES && i != index ==> post2.page_array_seq@[i] =~= pre.page_array_seq@[i])
        && post2.page_array_seq@[index as int].addr =~= pre.page_array_seq@[index as int].addr
        && post2.page_array_seq@[index as int].state =~= pre.page_array_seq@[index as int].state
        && post2.page_array_seq@[index as int].is_io_page =~= pre.page_array_seq@[index as int].is_io_page
        && post2.page_array_seq@[index as int].ref_count =~= pre.page_array_seq@[index as int].ref_count
        && post2.page_array_seq@[index as int].owning_container =~= new_oc
    {
        // Pointwise equality, with explicit case split at i == index.
        assert forall |i: int| 0 <= i < NUM_PAGES implies
            post1.page_array_seq@[i] =~= post2.page_array_seq@[i]
        by {
            if i == index as int {
                // Both have all 5 fields pinned identically: record
                // extensionality closes this.
                assert(post1.page_array_seq@[i].addr ==
                       post2.page_array_seq@[i].addr);
                assert(post1.page_array_seq@[i].state ==
                       post2.page_array_seq@[i].state);
                assert(post1.page_array_seq@[i].is_io_page ==
                       post2.page_array_seq@[i].is_io_page);
                assert(post1.page_array_seq@[i].ref_count ==
                       post2.page_array_seq@[i].ref_count);
                assert(post1.page_array_seq@[i].owning_container ==
                       post2.page_array_seq@[i].owning_container);
            } else {
                // Off-index: both equal pre[i].
                assert(post1.page_array_seq@[i] =~= pre.page_array_seq@[i]);
                assert(post2.page_array_seq@[i] =~= pre.page_array_seq@[i]);
            }
        };
        // Seq extensionality from pointwise + length equality.
        assert(post1.page_array_seq@ =~= post2.page_array_seq@);
    }
    // ====== END LLM-INSERTED ======
}

}
