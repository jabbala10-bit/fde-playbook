# The FAANG DSA Pattern Library

### ~22 patterns that cover the large majority of coding-interview problems

Every template below is **tested and passing**. Interviews aren't a memory test of these — they're a test of whether you can *recognize which pattern a disguised problem maps to*, then adapt the template. So the highest-value page is the recognition index. Learn to read the signal first; the code is muscle memory you build by reps.

> Companion to *The Decision-Driven Engineer*. Use the "reverse-engineer complexity from the input bound" trick (Part 1 there) alongside this: the constraint tells you the target Big-O, and the Big-O narrows the pattern.

---

## The Recognition Index — signal → pattern

| When you see... | Reach for | # |
|---|---|---|
| Sorted array, find a pair/triplet | Two Pointers | 1 |
| Longest/shortest substring/subarray with a constraint | Sliding Window | 2 |
| Linked list cycle, or "find middle" | Fast & Slow Pointers | 3 |
| Overlapping intervals, merging, scheduling | Merge Intervals | 4 |
| Array of 1..n, find missing/duplicate, **O(1) space** | Cyclic Sort | 5 |
| Reverse / reorder a linked list in place | In-place LL Reversal | 6 |
| Tree/graph level-by-level, shortest unweighted path | BFS | 7 |
| Tree/graph explore-all, connected components, paths | DFS | 8 |
| Subsets, permutations, combinations, "all ways" | Backtracking | 9 |
| Sorted input, or "minimize the max / maximize the min" | Binary Search (+ on answer) | 10 |
| "Top K", "K largest/smallest/most frequent" | Heap / Top-K | 11 |
| Merge K sorted lists/streams | K-way Merge | 12 |
| "Next greater/smaller element", spans, histograms | Monotonic Stack | 13 |
| Ordering with prerequisites/dependencies (DAG) | Topological Sort | 14 |
| Grouping, connectivity, "are these connected" | Union-Find (DSU) | 15 |
| Prefix search, autocomplete, word dictionary | Trie | 16 |
| "Max/min/count of ways" over a 1D sequence | DP — 1D | 17 |
| Two sequences, grids, knapsack, edit distance | DP — 2D | 18 |
| Weighted shortest path, non-negative edges | Dijkstra | 19 |
| Single number, subsets via bits, flags, XOR tricks | Bit Manipulation | 20 |
| Repeated range-sum / range queries | Prefix Sum | 21 |
| "Max non-overlapping", "min removals", local-optimal | Greedy | 22 |

---

## 1 · Two Pointers
**Recognize:** sorted array, pair/triplet with a target, or converging from both ends. **Complexity:** O(n) time, O(1) space.
```python
def two_sum_sorted(arr, target):
    lo, hi = 0, len(arr) - 1
    while lo < hi:
        s = arr[lo] + arr[hi]
        if s == target: return [lo, hi]
        if s < target:  lo += 1
        else:           hi -= 1
    return []
```
*Canonical:* Two Sum II, 3Sum, Container With Most Water, Trapping Rain Water.

## 2 · Sliding Window
**Recognize:** longest/shortest/count of a contiguous window meeting a constraint. Grow right, shrink left. **Complexity:** O(n).
```python
def longest_unique(s):
    seen, left, best = {}, 0, 0
    for right, ch in enumerate(s):
        if ch in seen and seen[ch] >= left:
            left = seen[ch] + 1          # jump left past the duplicate
        seen[ch] = right
        best = max(best, right - left + 1)
    return best
```
*Canonical:* Longest Substring Without Repeating, Min Window Substring, Max Sum Subarray of size k.

## 3 · Fast & Slow Pointers
**Recognize:** cycle detection, find middle, nth-from-end in a linked list. **Complexity:** O(n), O(1) space.
```python
def has_cycle(head):
    slow = fast = head
    while fast and fast.next:
        slow, fast = slow.next, fast.next.next
        if slow is fast: return True
    return False
```
*Canonical:* Linked List Cycle, Find the Duplicate Number, Happy Number, Middle of List.

## 4 · Merge Intervals
**Recognize:** intervals that overlap and must be merged/inserted/counted. **Sort by start**, then sweep. **Complexity:** O(n log n).
```python
def merge(intervals):
    intervals.sort(key=lambda x: x[0])
    out = []
    for s, e in intervals:
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out
```
*Canonical:* Merge Intervals, Insert Interval, Meeting Rooms I/II.

## 5 · Cyclic Sort
**Recognize:** array holds numbers in range **1..n**; find missing/duplicate/misplaced in **O(1) space**. Place each value at its index. **Complexity:** O(n).
```python
def cyclic_sort(nums):
    i = 0
    while i < len(nums):
        j = nums[i] - 1
        if 0 <= j < len(nums) and nums[i] != nums[j]:
            nums[i], nums[j] = nums[j], nums[i]
        else:
            i += 1
    return nums
```
*Canonical:* Missing Number, Find All Duplicates, First Missing Positive.

## 6 · In-place Linked List Reversal
**Recognize:** reverse a list or a sub-section, reorder nodes without extra space. **Complexity:** O(n), O(1) space.
```python
def reverse(head):
    prev, cur = None, head
    while cur:
        nxt = cur.next
        cur.next = prev
        prev, cur = cur, nxt
    return prev
```
*Canonical:* Reverse Linked List, Reverse Nodes in k-Group, Reorder List.

## 7 · BFS (level order)
**Recognize:** shortest path in an unweighted graph, or process a tree level by level. **Complexity:** O(V+E).
```python
from collections import deque
def level_order(root):
    if not root: return []
    q, res = deque([root]), []
    while q:
        level = []
        for _ in range(len(q)):          # snapshot the level
            node = q.popleft()
            level.append(node.val)
            if node.left:  q.append(node.left)
            if node.right: q.append(node.right)
        res.append(level)
    return res
```
*Canonical:* Binary Tree Level Order, Rotting Oranges, Word Ladder, shortest path in a grid.

## 8 · DFS
**Recognize:** explore all paths, count components, detect cycles, flood fill. **Complexity:** O(V+E).
```python
def dfs(graph, start):
    visited = set()
    def go(node):
        visited.add(node)
        for nb in graph[node]:
            if nb not in visited:
                go(nb)
    go(start)
    return visited
```
*Canonical:* Number of Islands, Clone Graph, Course Schedule (cycle check), Path Sum.

## 9 · Backtracking
**Recognize:** generate **all** subsets/permutations/combinations; constraint satisfaction. Choose → recurse → un-choose. **Complexity:** exponential (that's expected — check n is small).
```python
def subsets(nums):
    res = []
    def bt(start, path):
        res.append(path[:])
        for i in range(start, len(nums)):
            path.append(nums[i])
            bt(i + 1, path)
            path.pop()                    # undo the choice
    bt(0, [])
    return res

def permute(nums):
    res = []
    def bt(path, rem):
        if not rem:
            res.append(path[:]); return
        for i in range(len(rem)):
            bt(path + [rem[i]], rem[:i] + rem[i+1:])
    bt([], nums)
    return res
```
*Canonical:* Subsets, Permutations, Combination Sum, N-Queens, Word Search, Generate Parentheses.

## 10 · Binary Search (incl. on the answer)
**Recognize:** sorted data, OR "minimize the maximum / maximize the minimum / smallest x that works". The second form is the senior signal. **Complexity:** O(log n) × cost of the check.
```python
def binary_search(arr, target):
    lo, hi = 0, len(arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target: return mid
        if arr[mid] < target:  lo = mid + 1
        else:                  hi = mid - 1
    return -1

def min_feasible(lo, hi, feasible):        # search on the answer space
    while lo < hi:
        mid = (lo + hi) // 2
        if feasible(mid): hi = mid          # mid works, try smaller
        else:             lo = mid + 1
    return lo
```
*Canonical:* Search in Rotated Array, Koko Eating Bananas, Split Array Largest Sum, Ship Packages in D Days.

## 11 · Top-K / Heap
**Recognize:** "K largest/smallest/most frequent", or a running median. Keep a heap of size k. **Complexity:** O(n log k).
```python
import heapq
def top_k_heap(nums, k):
    h = []
    for n in nums:
        heapq.heappush(h, n)
        if len(h) > k: heapq.heappop(h)     # min-heap keeps k largest
    return sorted(h)
```
*Canonical:* Kth Largest Element, Top K Frequent, Find Median from Data Stream (two heaps).

## 12 · K-way Merge
**Recognize:** merge K sorted lists/streams; smallest-across-lists repeatedly. Heap of one head per list. **Complexity:** O(N log k).
```python
import heapq
def merge_k(lists):
    h = []
    for i, lst in enumerate(lists):
        if lst: heapq.heappush(h, (lst[0], i, 0))
    out = []
    while h:
        val, i, j = heapq.heappop(h)
        out.append(val)
        if j + 1 < len(lists[i]):
            heapq.heappush(h, (lists[i][j+1], i, j+1))
    return out
```
*Canonical:* Merge k Sorted Lists, Smallest Range Covering K Lists, Kth Smallest in Sorted Matrix.

## 13 · Monotonic Stack
**Recognize:** "next/previous greater or smaller element", spans, histogram areas. Stack keeps a monotonic run of indices. **Complexity:** O(n) amortized.
```python
def next_greater(nums):
    res = [-1] * len(nums)
    stack = []                              # indices, values decreasing
    for i, n in enumerate(nums):
        while stack and nums[stack[-1]] < n:
            res[stack.pop()] = n
        stack.append(i)
    return res
```
*Canonical:* Daily Temperatures, Next Greater Element, Largest Rectangle in Histogram, Trapping Rain Water.

## 14 · Topological Sort (Kahn's)
**Recognize:** ordering with dependencies/prerequisites on a DAG; also detects cycles (empty result ⇒ cycle). **Complexity:** O(V+E).
```python
from collections import deque
def topo_sort(n, edges):
    graph = [[] for _ in range(n)]
    indeg = [0] * n
    for u, v in edges:
        graph[u].append(v); indeg[v] += 1
    q = deque(i for i in range(n) if indeg[i] == 0)
    order = []
    while q:
        u = q.popleft(); order.append(u)
        for v in graph[u]:
            indeg[v] -= 1
            if indeg[v] == 0: q.append(v)
    return order if len(order) == n else []  # [] means a cycle exists
```
*Canonical:* Course Schedule I/II, Alien Dictionary, Build Order.

## 15 · Union-Find (DSU)
**Recognize:** dynamic connectivity, grouping, "are a and b connected", cycle detection in undirected graphs. Path compression + union by rank ⇒ ~O(1). **Complexity:** ~O(α(n)) per op.
```python
class DSU:
    def __init__(self, n):
        self.p = list(range(n)); self.r = [0] * n
    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]    # path compression
            x = self.p[x]
        return x
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb: return False            # already connected (a cycle)
        if self.r[ra] < self.r[rb]: ra, rb = rb, ra
        self.p[rb] = ra
        if self.r[ra] == self.r[rb]: self.r[ra] += 1
        return True
```
*Canonical:* Number of Connected Components, Redundant Connection, Accounts Merge, Kruskal's MST.

## 16 · Trie
**Recognize:** prefix search, autocomplete, dictionary of words, wildcard match. **Complexity:** O(L) per op (L = word length).
```python
class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end = False

class Trie:
    def __init__(self): self.root = TrieNode()
    def insert(self, word):
        node = self.root
        for ch in word:
            node = node.children.setdefault(ch, TrieNode())
        node.is_end = True
    def search(self, word):
        node = self.root
        for ch in word:
            if ch not in node.children: return False
            node = node.children[ch]
        return node.is_end
```
*Canonical:* Implement Trie, Word Search II, Design Add & Search Words, Autocomplete.

## 17 · DP — 1D
**Recognize:** max/min/count of ways over a linear sequence where each state depends on a few previous ones. Roll two variables. **Complexity:** O(n) time, O(1) space.
```python
def rob(nums):                              # house robber: no two adjacent
    prev, cur = 0, 0
    for n in nums:
        prev, cur = cur, max(cur, prev + n)
    return cur
```
*Canonical:* Climbing Stairs, House Robber, Max Subarray (Kadane), Decode Ways, Coin Change.

## 18 · DP — 2D
**Recognize:** two sequences, grids, or knapsack (item × capacity). Build a table from smaller subproblems. **Complexity:** O(m·n).
```python
def lcs(a, b):                              # longest common subsequence
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i-1] == b[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    return dp[m][n]
```
*Canonical:* Edit Distance, LCS, Unique Paths, 0/1 Knapsack, Longest Palindromic Subsequence.

## 19 · Dijkstra
**Recognize:** shortest path with **non-negative** weights. (Negative edges ⇒ Bellman-Ford; unweighted ⇒ plain BFS.) **Complexity:** O(E log V).
```python
import heapq
def dijkstra(graph, src, n):                # graph[u] = list of (v, weight)
    dist = [float('inf')] * n
    dist[src] = 0
    pq = [(0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]: continue            # stale entry, skip
        for v, w in graph[u]:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                heapq.heappush(pq, (dist[v], v))
    return dist
```
*Canonical:* Network Delay Time, Cheapest Flights (k stops), Path With Min Effort, Swim in Rising Water.

## 20 · Bit Manipulation
**Recognize:** "single number", subset enumeration, flags/masks, no-extra-space parity tricks.
```python
x & (x - 1)         # drop the lowest set bit
x & (-x)            # isolate the lowest set bit
x ^ y               # differing bits;  a ^ a == 0  ->  find the lone element
bin(x).count('1')   # popcount (number of set bits)
(x >> i) & 1        # read the i-th bit
```
*Canonical:* Single Number, Counting Bits, Subsets (bitmask), Sum of Two Integers, Missing Number.

## 21 · Prefix Sum
**Recognize:** repeated range-sum queries, subarray-sum-equals-k, running totals. Precompute cumulative sums; a range is one subtraction. **Complexity:** O(n) build, O(1) per query.
```python
def build_prefix(nums):
    prefix = [0]
    for n in nums:
        prefix.append(prefix[-1] + n)
    return prefix
# sum of nums[i..j] inclusive = prefix[j+1] - prefix[i]
```
*Canonical:* Range Sum Query, Subarray Sum Equals K, Product of Array Except Self (prefix/suffix), Pivot Index.

## 22 · Greedy
**Recognize:** a locally optimal choice provably leads to the global optimum — often "max non-overlapping" or "min removals". The trick is usually **what to sort by**. **Complexity:** O(n log n).
```python
def max_meetings(intervals):                # max non-overlapping intervals
    intervals.sort(key=lambda x: x[1])       # sort by END time
    count, end = 0, float('-inf')
    for s, e in intervals:
        if s >= end:
            count += 1
            end = e
    return count
```
*Canonical:* Jump Game, Non-overlapping Intervals, Task Scheduler, Gas Station, Partition Labels.

---

## How to actually drill this (so it sticks)

1. **Recognition before code.** For each new problem, *first* say out loud which pattern it is and why — before writing anything. That's the exact skill the interview grades. Getting the mapping right is 80% of the solve.
2. **Rebuild each template from scratch** until muscle memory — don't re-read, re-derive. You want to produce the skeleton in ~60 seconds without thinking.
3. **Map every problem you solve back to this index.** After solving, tag it with its pattern. After ~150 tagged problems the disguises stop working on you.
4. **Combine patterns.** Hard problems are usually two patterns stacked (e.g. binary-search-on-answer + a greedy feasibility check; BFS + a heap). Once singles are automatic, practice the pairs.
5. **Always finish the ritual** from the main guide (Part 7): clarify → brute force → optimize → code → test → complexity. The pattern gets you to the optimized step; the ritual gets you the offer.

> Coverage note: these ~22 cover the large majority of what shows up, but not literally everything — segment trees / Fenwick, advanced graph (Bellman-Ford, min-cut/max-flow, MST), matrix exponentiation, and string algorithms (KMP, suffix structures) show up in the hardest rounds. Add them once these are automatic.
