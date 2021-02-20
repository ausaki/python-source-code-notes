# Python中的 Dict


## 散列函数


## 开放寻址算法

原文：

/*
Major subtleties ahead:  Most hash schemes depend on having a "good" hash
function, in the sense of simulating randomness.  Python doesn't:  its most
important hash functions (for strings and ints) are very regular in common
cases:
```
>>> map(hash, (0, 1, 2, 3))
[0, 1, 2, 3]
>>> map(hash, ("namea", "nameb", "namec", "named"))
[-1658398457, -1658398460, -1658398459, -1658398462]
>>>
```
This isn't necessarily bad!  To the contrary, in a table of size 2**i, taking
the low-order i bits as the initial table index is extremely fast, and there
are no collisions at all for dicts indexed by a contiguous range of ints.
The same is approximately true when keys are "consecutive" strings.  So this
gives better-than-random behavior in common cases, and that's very desirable.

OTOH, when collisions occur, the tendency to fill contiguous slices of the
hash table makes a good collision resolution strategy crucial.  Taking only
the last i bits of the hash code is also vulnerable:  for example, consider
[i << 16 for i in range(20000)] as a set of keys.  Since ints are their own
hash codes, and this fits in a dict of size 2**15, the last 15 bits of every
hash code are all 0:  they *all* map to the same table index.

But catering to unusual cases should not slow the usual ones, so we just take
the last i bits anyway.  It's up to collision resolution to do the rest.  If
we *usually* find the key we're looking for on the first try (and, it turns
out, we usually do -- the table load factor is kept under 2/3, so the odds
are solidly in our favor), then it makes best sense to keep the initial index
computation dirt cheap.

The first half of collision resolution is to visit table indices via this
recurrence:

    j = ((5*j) + 1) mod 2**i

For any initial j in range(2**i), repeating that 2**i times generates each
int in range(2**i) exactly once (see any text on random-number generation for
proof).  By itself, this doesn't help much:  like linear probing (setting
j += 1, or j -= 1, on each loop trip), it scans the table entries in a fixed
order.  This would be bad, except that's not the only thing we do, and it's
actually *good* in the common cases where hash keys are consecutive.  In an
example that's really too small to make this entirely clear, for a table of
size 2**3 the order of indices is:

    0 -> 1 -> 6 -> 7 -> 4 -> 5 -> 2 -> 3 -> 0 [and here it's repeating]

If two things come in at index 5, the first place we look after is index 2,
not 6, so if another comes in at index 6 the collision at 5 didn't hurt it.
Linear probing is deadly in this case because there the fixed probe order
is the *same* as the order consecutive keys are likely to arrive.  But it's
extremely unlikely hash codes will follow a 5*j+1 recurrence by accident,
and certain that consecutive hash codes do not.

The other half of the strategy is to get the other bits of the hash code
into play.  This is done by initializing a (unsigned) vrbl "perturb" to the
full hash code, and changing the recurrence to:

    j = (5*j) + 1 + perturb;
    perturb >>= PERTURB_SHIFT;
    use j % 2**i as the next table index;

Now the probe sequence depends (eventually) on every bit in the hash code,
and the pseudo-scrambling property of recurring on 5*j+1 is more valuable,
because it quickly magnifies small differences in the bits that didn't affect
the initial index.  Note that because perturb is unsigned, if the recurrence
is executed often enough perturb eventually becomes and remains 0.  At that
point (very rarely reached) the recurrence is on (just) 5*j+1 again, and
that's certain to find an empty slot eventually (since it generates every int
in range(2**i), and we make sure there's always at least one empty slot).

Selecting a good value for PERTURB_SHIFT is a balancing act.  You want it
small so that the high bits of the hash code continue to affect the probe
sequence across iterations; but you want it large so that in really bad cases
the high-order hash bits have an effect on early iterations.  5 was "the
best" in minimizing total collisions across experiments Tim Peters ran (on
both normal and pathological cases), but 4 and 6 weren't significantly worse.

Historical:  Reimer Behrends contributed the idea of using a polynomial-based
approach, using repeated multiplication by x in GF(2**n) where an irreducible
polynomial for each table size was chosen such that x was a primitive root.
Christian Tismer later extended that to use division by x instead, as an
efficient way to get the high bits of the hash code into play.  This scheme
also gave excellent collision statistics, but was more expensive:  two
if-tests were required inside the loop; computing "the next" index took about
the same number of operations but without as much potential parallelism
(e.g., computing 5*j can go on at the same time as computing 1+perturb in the
above, and then shifting perturb can be done while the table index is being
masked); and the dictobject struct required a member to hold the table's
polynomial.  In Tim's experiments the current scheme ran faster, produced
equally good collision statistics, needed less code & used less memory.

Theoretical Python 2.5 headache:  hash codes are only C "long", but
sizeof(Py_ssize_t) > sizeof(long) may be possible.  In that case, and if a
dict is genuinely huge, then only the slots directly reachable via indexing
by a C long can be the first slot in a probe sequence.  The probe sequence
will still eventually reach every slot in the table, but the collision rate
on initial probes may be much higher than this scheme was designed for.
Getting a hash code as fat as Py_ssize_t is the only real cure.  But in
practice, this probably won't make a lick of difference for many years (at
which point everyone will have terabytes of RAM on 64-bit boxes).
*/

大概意思是：

Python的哈希函数非常普通，整数的哈希值就是自身，例如：

```
>>> map(hash, (0, 1, 2, 3))
[0, 1, 2, 3]
>>> map(hash, ("namea", "nameb", "namec", "named"))
[-1658398457, -1658398460, -1658398459, -1658398462]
>>>
```

假如哈希表的长度为`2 ** i`，Python 使用哈希值低位的 i 个 bits 作为初始索引值，即`index = hash & (2 ** i - 1)`。
使用这个算法确定初始索引的效率非常高，假如dict 的 key都是一些连续整数或者字符串的话，将不会出现索引碰撞，因为它们的初始索引都会落在不同的位置。

在另一方面，这个算法也有不足的地方，例如：
对于大小为2 ** 15的 dict，有一些这样的key：[i << 16 for i in range(20000)]，那么它们的索引都将等于0。

假如发生索引碰撞，使用下面这个公式计算下一个索引：

`j = ((5*j) + 1) mod 2**i`


## 搜索算法

原文：


The basic lookup function used by all operations.
This is based on Algorithm D from Knuth Vol. 3, Sec. 6.4.
Open addressing is preferred over chaining since the link overhead for
chaining would be substantial (100% with typical malloc overhead).

**The initial probe index is computed as hash mod the table size. Subsequent
probe indices are computed as explained earlier.**

All arithmetic on hash should ignore overflow.

(The details in this version are due to Tim Peters, building on many past
contributions by Reimer Behrends, Jyrki Alakuijala, Vladimir Marangozov and
Christian Tismer).

lookdict() is general-purpose, and may return NULL if (and only if) a
comparison raises an exception (this was new in Python 2.5).
lookdict_string() below is specialized to string keys, comparison of which can
never raise an exception; that function can never return NULL.  For both, when
the key isn't found a dictentry* is returned for which the me_value field is
NULL; this is the slot in the dict at which the key would have been found, and
the caller can (if it wishes) add the <key, value> pair to the returned
dictentry*.


## 其它信息（摘自Python2.5源码/Objects/dictnotes.txt）

NOTES ON OPTIMIZING DICTIONARIES
================================


Principal Use Cases for Dictionaries
------------------------------------

Passing keyword arguments
    Typically, one read and one write for 1 to 3 elements.
    Occurs frequently in normal python code.

Class method lookup
    Dictionaries vary in size with 8 to 16 elements being common.
    Usually written once with many lookups.
    When base classes are used, there are many failed lookups
        followed by a lookup in a base class.

Instance attribute lookup and Global variables
    Dictionaries vary in size.  4 to 10 elements are common.
    Both reads and writes are common.

Builtins
    Frequent reads.  Almost never written.
    Size 126 interned strings (as of Py2.3b1).
    A few keys are accessed much more frequently than others.

Uniquification
    Dictionaries of any size.  Bulk of work is in creation.
    Repeated writes to a smaller set of keys.
    Single read of each key.
    Some use cases have two consecutive accesses to the same key.

    * Removing duplicates from a sequence.
        dict.fromkeys(seqn).keys()

    * Counting elements in a sequence.
        for e in seqn:
          d[e] = d.get(e,0) + 1

    * Accumulating references in a dictionary of lists:

        for pagenumber, page in enumerate(pages):
          for word in page:
            d.setdefault(word, []).append(pagenumber)

    Note, the second example is a use case characterized by a get and set
    to the same key.  There are similar used cases with a __contains__
    followed by a get, set, or del to the same key.  Part of the
    justification for d.setdefault is combining the two lookups into one.

Membership Testing
    Dictionaries of any size.  Created once and then rarely changes.
    Single write to each key.
    Many calls to __contains__() or has_key().
    Similar access patterns occur with replacement dictionaries
        such as with the % formatting operator.

Dynamic Mappings
    Characterized by deletions interspersed with adds and replacements.
    Performance benefits greatly from the re-use of dummy entries.


Data Layout (assuming a 32-bit box with 64 bytes per cache line)
----------------------------------------------------------------

Smalldicts (8 entries) are attached to the dictobject structure
and the whole group nearly fills two consecutive cache lines.

Larger dicts use the first half of the dictobject structure (one cache
line) and a separate, continuous block of entries (at 12 bytes each
for a total of 5.333 entries per cache line).


Tunable Dictionary Parameters
-----------------------------

* PyDict_MINSIZE.  Currently set to 8.
    Must be a power of two.  New dicts have to zero-out every cell.
    Each additional 8 consumes 1.5 cache lines.  Increasing improves
    the sparseness of small dictionaries but costs time to read in
    the additional cache lines if they are not already in cache.
    That case is common when keyword arguments are passed.

* Maximum dictionary load in PyDict_SetItem.  Currently set to 2/3.
    Increasing this ratio makes dictionaries more dense resulting
    in more collisions.  Decreasing it improves sparseness at the
    expense of spreading entries over more cache lines and at the
    cost of total memory consumed.

    The load test occurs in highly time sensitive code.  Efforts
    to make the test more complex (for example, varying the load
    for different sizes) have degraded performance.

* Growth rate upon hitting maximum load.  Currently set to *2.
    Raising this to *4 results in half the number of resizes,
    less effort to resize, better sparseness for some (but not
    all dict sizes), and potentially doubles memory consumption
    depending on the size of the dictionary.  Setting to *4
    eliminates every other resize step.

Tune-ups should be measured across a broad range of applications and
use cases.  A change to any parameter will help in some situations and
hurt in others.  The key is to find settings that help the most common
cases and do the least damage to the less common cases.  Results will
vary dramatically depending on the exact number of keys, whether the
keys are all strings, whether reads or writes dominate, the exact
hash values of the keys (some sets of values have fewer collisions than
others).  Any one test or benchmark is likely to prove misleading.

While making a dictionary more sparse reduces collisions, it impairs
iteration and key listing.  Those methods loop over every potential
entry.  Doubling the size of dictionary results in twice as many
non-overlapping memory accesses for keys(), items(), values(),
__iter__(), iterkeys(), iteritems(), itervalues(), and update().
Also, every dictionary iterates at least twice, once for the memset()
when it is created and once by dealloc().


Results of Cache Locality Experiments
-------------------------------------

When an entry is retrieved from memory, 4.333 adjacent entries are also
retrieved into a cache line.  Since accessing items in cache is *much*
cheaper than a cache miss, an enticing idea is to probe the adjacent
entries as a first step in collision resolution.  Unfortunately, the
introduction of any regularity into collision searches results in more
collisions than the current random chaining approach.

Exploiting cache locality at the expense of additional collisions fails
to payoff when the entries are already loaded in cache (the expense
is paid with no compensating benefit).  This occurs in small dictionaries
where the whole dictionary fits into a pair of cache lines.  It also
occurs frequently in large dictionaries which have a common access pattern
where some keys are accessed much more frequently than others.  The
more popular entries *and* their collision chains tend to remain in cache.

To exploit cache locality, change the collision resolution section
in lookdict() and lookdict_string().  Set i^=1 at the top of the
loop and move the  i = (i << 2) + i + perturb + 1 to an unrolled
version of the loop.

This optimization strategy can be leveraged in several ways:

* If the dictionary is kept sparse (through the tunable parameters),
then the occurrence of additional collisions is lessened.

* If lookdict() and lookdict_string() are specialized for small dicts
and for largedicts, then the versions for large_dicts can be given
an alternate search strategy without increasing collisions in small dicts
which already have the maximum benefit of cache locality.

* If the use case for a dictionary is known to have a random key
access pattern (as opposed to a more common pattern with a Zipf's law
distribution), then there will be more benefit for large dictionaries
because any given key is no more likely than another to already be
in cache.

* In use cases with paired accesses to the same key, the second access
is always in cache and gets no benefit from efforts to further improve
cache locality.

Optimizing the Search of Small Dictionaries
-------------------------------------------

If lookdict() and lookdict_string() are specialized for smaller dictionaries,
then a custom search approach can be implemented that exploits the small
search space and cache locality.

* The simplest example is a linear search of contiguous entries.  This is
  simple to implement, guaranteed to terminate rapidly, never searches
  the same entry twice, and precludes the need to check for dummy entries.

* A more advanced example is a self-organizing search so that the most
  frequently accessed entries get probed first.  The organization
  adapts if the access pattern changes over time.  Treaps are ideally
  suited for self-organization with the most common entries at the
  top of the heap and a rapid binary search pattern.  Most probes and
  results are all located at the top of the tree allowing them all to
  be located in one or two cache lines.

* Also, small dictionaries may be made more dense, perhaps filling all
  eight cells to take the maximum advantage of two cache lines.


Strategy Pattern
----------------

Consider allowing the user to set the tunable parameters or to select a
particular search method.  Since some dictionary use cases have known
sizes and access patterns, the user may be able to provide useful hints.

1) For example, if membership testing or lookups dominate runtime and memory
   is not at a premium, the user may benefit from setting the maximum load
   ratio at 5% or 10% instead of the usual 66.7%.  This will sharply
   curtail the number of collisions but will increase iteration time.
   The builtin namespace is a prime example of a dictionary that can
   benefit from being highly sparse.

2) Dictionary creation time can be shortened in cases where the ultimate
   size of the dictionary is known in advance.  The dictionary can be
   pre-sized so that no resize operations are required during creation.
   Not only does this save resizes, but the key insertion will go
   more quickly because the first half of the keys will be inserted into
   a more sparse environment than before.  The preconditions for this
   strategy arise whenever a dictionary is created from a key or item
   sequence and the number of *unique* keys is known.

3) If the key space is large and the access pattern is known to be random,
   then search strategies exploiting cache locality can be fruitful.
   The preconditions for this strategy arise in simulations and
   numerical analysis.

4) If the keys are fixed and the access pattern strongly favors some of
   the keys, then the entries can be stored contiguously and accessed
   with a linear search or treap.  This exploits knowledge of the data,
   cache locality, and a simplified search routine.  It also eliminates
   the need to test for dummy entries on each probe.  The preconditions
   for this strategy arise in symbol tables and in the builtin dictionary.


Readonly Dictionaries
---------------------
Some dictionary use cases pass through a build stage and then move to a
more heavily exercised lookup stage with no further changes to the
dictionary.

An idea that emerged on python-dev is to be able to convert a dictionary
to a read-only state.  This can help prevent programming errors and also
provide knowledge that can be exploited for lookup optimization.

The dictionary can be immediately rebuilt (eliminating dummy entries),
resized (to an appropriate level of sparseness), and the keys can be
jostled (to minimize collisions).  The lookdict() routine can then
eliminate the test for dummy entries (saving about 1/4 of the time
spent in the collision resolution loop).

An additional possibility is to insert links into the empty spaces
so that dictionary iteration can proceed in len(d) steps instead of
(mp->mask + 1) steps.  Alternatively, a separate tuple of keys can be
kept just for iteration.


Caching Lookups
---------------
The idea is to exploit key access patterns by anticipating future lookups
based on previous lookups.

The simplest incarnation is to save the most recently accessed entry.
This gives optimal performance for use cases where every get is followed
by a set or del to the same key.
