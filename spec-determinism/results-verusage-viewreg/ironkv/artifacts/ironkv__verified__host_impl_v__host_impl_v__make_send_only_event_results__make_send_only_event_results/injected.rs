use vstd::prelude::*;
use vstd::seq_lib::*;


fn main(){}

verus! {



pub struct EventResults {
    // What netc actually observed:
    pub recvs: Seq<NetEvent>,
    pub clocks: Seq<NetEvent>,
    pub sends: Seq<NetEvent>,

    /// What we were trying to make happen:
    /// ios may claim an event that doesn't appear in event_seq() if, say, the netc socket broke on
    /// send. We already received, so the only way we can refine is by claiming we finished the
    /// corresponding send (in ios). In this case, the postcondition of next_ensures gives
    /// us the out because !netc.ok allows ios!=event_seq().
    pub ios: Ios,
}

impl EventResults {
 
    pub open spec fn event_seq(self) -> Seq<NetEvent> {
        self.recvs + self.clocks + self.sends
    }

    pub open spec fn well_typed_events(self) -> bool {
        &&& forall |i| 0 <= i < self.recvs.len() ==> self.recvs[i] is Receive
        &&& forall |i| 0 <= i < self.clocks.len() ==> self.clocks[i] is ReadClock || self.clocks[i] is TimeoutReceive
        &&& forall |i| 0 <= i < self.sends.len() ==> self.sends[i] is Send
        &&& self.clocks.len() <= 1
    }

}


pub fn make_send_only_event_results(net_events: Ghost<Seq<NetEvent>>) -> (res: Ghost<EventResults>)
    requires
        forall |i: int| 0 <= i && i < net_events@.len() ==> net_events@[i] is Send
    ensures
        res@.recvs == Seq::<NetEvent>::empty(),
        res@.clocks == Seq::<NetEvent>::empty(),
        res@.sends == net_events@,
        res@.ios == net_events@,
        res@.event_seq() == net_events@,
        res@.well_typed_events(),
{
    let ghost res = EventResults {
        recvs: Seq::<NetEvent>::empty(),
        clocks: Seq::<NetEvent>::empty(),
        sends: net_events@,
        ios: net_events@,
    };
    assert (forall |i| 0 <= i < res.recvs.len() ==> res.recvs[i] is Receive);
    assert (forall |i| 0 <= i < res.clocks.len() ==> res.clocks[i] is ReadClock || res.clocks[i] is TimeoutReceive);
    assert (forall |i| 0 <= i < res.sends.len() ==> res.sends[i] is Send);
    assert (res.clocks.len() <= 1);
    assert (res.well_typed_events());
    proof { assert_seqs_equal!(res.event_seq(), net_events@); };
    Ghost(res)
}

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

#[derive(Eq,PartialEq,Hash)]
pub struct SHTKey {
    pub // workaround
        ukey: u64,
}
pub type AbstractKey = SHTKey;
pub type AbstractValue = Seq<u8>;
pub type Hashtable = Map<AbstractKey, AbstractValue>;

pub trait KeyTrait : Sized {}
pub trait VerusClone : Sized {}


pub struct KeyRange<K: KeyTrait + VerusClone>{
    pub lo: KeyIterator<K>,
    pub hi: KeyIterator<K>,
}

pub struct KeyIterator<K: KeyTrait + VerusClone>{
    // None means we hit the end
    pub k: Option<K>,
}

impl<K: VerusClone + KeyTrait> VerusClone for KeyIterator<K> {
}

impl<K: VerusClone + KeyTrait> VerusClone for KeyRange<K> {
}

impl KeyTrait for SHTKey {
}

impl VerusClone for SHTKey {
}

pub struct LPacket<IdType, MessageType> {
    pub dst: IdType,
    pub src: IdType,
    pub msg: MessageType,
}

pub enum LIoOp<IdType, MessageType> {
    Send{s: LPacket<IdType, MessageType>},
    Receive{r: LPacket<IdType, MessageType>},
    TimeoutReceive{},
    ReadClock{t: int},
}


pub type NetEvent = LIoOp<AbstractEndPoint, Seq<u8>>;

type Ios = Seq<NetEvent>;

// === INJECTED DET CHECK ===
// L4-llm view declarations (generated, see view_registry cache)
pub struct EventResultsView {
    pub recvs: Seq<NetEvent>,
    pub clocks: Seq<NetEvent>,
    pub sends: Seq<NetEvent>,
    pub ios: Ios,
}

impl View for EventResults {
    type V = EventResultsView;
    closed spec fn view(&self) -> EventResultsView {
        EventResultsView {
            recvs: self.recvs,
            clocks: self.clocks,
            sends: self.sends,
            ios: self.ios,
        }
    }
}

// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_make_send_only_event_results_equal(r1: Ghost<EventResults>, r2: Ghost<EventResults>) -> bool {
    ((((r1)@).view() == ((r2)@).view()))
}

proof fn det_make_send_only_event_results(g__net_events___leneq: bool, k__net_events___leneq: nat, g__net_events___lenrng: bool, k__net_events___lenrng_lo: nat, k__net_events___lenrng_hi: nat, g__r1___recvs_leneq: bool, k__r1___recvs_leneq: nat, g__r1___recvs_lenrng: bool, k__r1___recvs_lenrng_lo: nat, k__r1___recvs_lenrng_hi: nat, g__r1___clocks_leneq: bool, k__r1___clocks_leneq: nat, g__r1___clocks_lenrng: bool, k__r1___clocks_lenrng_lo: nat, k__r1___clocks_lenrng_hi: nat, g__r1___sends_leneq: bool, k__r1___sends_leneq: nat, g__r1___sends_lenrng: bool, k__r1___sends_lenrng_lo: nat, k__r1___sends_lenrng_hi: nat, g__r2___recvs_leneq: bool, k__r2___recvs_leneq: nat, g__r2___recvs_lenrng: bool, k__r2___recvs_lenrng_lo: nat, k__r2___recvs_lenrng_hi: nat, g__r2___clocks_leneq: bool, k__r2___clocks_leneq: nat, g__r2___clocks_lenrng: bool, k__r2___clocks_lenrng_lo: nat, k__r2___clocks_lenrng_hi: nat, g__r2___sends_leneq: bool, k__r2___sends_leneq: nat, g__r2___sends_lenrng: bool, k__r2___sends_lenrng_lo: nat, k__r2___sends_lenrng_hi: nat, g_neq_tuple: bool, net_events: Ghost<Seq<NetEvent>>, r1: Ghost<EventResults>, r2: Ghost<EventResults>)
    requires (forall |i: int| 0 <= i && i < net_events@.len() ==> net_events@[i] is Send),
    ensures
        ({
            &&& (r1@.recvs == Seq::<NetEvent>::empty())
            &&& (r1@.clocks == Seq::<NetEvent>::empty())
            &&& (r1@.sends == net_events@)
            &&& (r1@.ios == net_events@)
            &&& (r1@.event_seq() == net_events@)
            &&& (r1@.well_typed_events())
            &&& (r2@.recvs == Seq::<NetEvent>::empty())
            &&& (r2@.clocks == Seq::<NetEvent>::empty())
            &&& (r2@.sends == net_events@)
            &&& (r2@.ios == net_events@)
            &&& (r2@.event_seq() == net_events@)
            &&& (r2@.well_typed_events())
        }) ==> det_make_send_only_event_results_equal(r1, r2),
{
    if g__net_events___leneq { assume((net_events)@.len() == k__net_events___leneq); }
    if g__net_events___lenrng { assume((net_events)@.len() >= k__net_events___lenrng_lo && (net_events)@.len() <= k__net_events___lenrng_hi); }
    if g__r1___recvs_leneq { assume((r1)@.recvs.len() == k__r1___recvs_leneq); }
    if g__r1___recvs_lenrng { assume((r1)@.recvs.len() >= k__r1___recvs_lenrng_lo && (r1)@.recvs.len() <= k__r1___recvs_lenrng_hi); }
    if g__r1___clocks_leneq { assume((r1)@.clocks.len() == k__r1___clocks_leneq); }
    if g__r1___clocks_lenrng { assume((r1)@.clocks.len() >= k__r1___clocks_lenrng_lo && (r1)@.clocks.len() <= k__r1___clocks_lenrng_hi); }
    if g__r1___sends_leneq { assume((r1)@.sends.len() == k__r1___sends_leneq); }
    if g__r1___sends_lenrng { assume((r1)@.sends.len() >= k__r1___sends_lenrng_lo && (r1)@.sends.len() <= k__r1___sends_lenrng_hi); }
    if g__r2___recvs_leneq { assume((r2)@.recvs.len() == k__r2___recvs_leneq); }
    if g__r2___recvs_lenrng { assume((r2)@.recvs.len() >= k__r2___recvs_lenrng_lo && (r2)@.recvs.len() <= k__r2___recvs_lenrng_hi); }
    if g__r2___clocks_leneq { assume((r2)@.clocks.len() == k__r2___clocks_leneq); }
    if g__r2___clocks_lenrng { assume((r2)@.clocks.len() >= k__r2___clocks_lenrng_lo && (r2)@.clocks.len() <= k__r2___clocks_lenrng_hi); }
    if g__r2___sends_leneq { assume((r2)@.sends.len() == k__r2___sends_leneq); }
    if g__r2___sends_lenrng { assume((r2)@.sends.len() >= k__r2___sends_lenrng_lo && (r2)@.sends.len() <= k__r2___sends_lenrng_hi); }
    if g_neq_tuple { assume(!det_make_send_only_event_results_equal(r1, r2)); }
}
// === END INJECTED ===

}
