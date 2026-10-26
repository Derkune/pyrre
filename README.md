# RRE

Functional esolang. Planned for an eventual graphical syntax and gamification.

## Example

This computes the Nth triangular number:

```
func main(n)
    raw = tri(n)
    return -(raw, 1)
endfunc

func tri(n)
    done = >(0, n)
    smaller = -(n, 1)
    rest = ?(done, tri(smaller))
    return +(n, rest)
endfunc
```

## Specification

### Types

There are 4 types: int, list, thunk, and error.

- Integers can be negative.
- Lists are immutable and can hold ints, other lists, and thunks.
- Thunks are like lists, containing argument values and metadata for the function to apply.
- Errors carry error messages. An error infects every operation, forcing it to output an error when evaluated. The exceptions are operations with 2 errors, where the messages are combined and propagated, and `?`, which leaves the second argument unevaluated until it is needed.

### Programs and functions

Programs are sequences of functions. Functions must have different names and must start with different letters (reserved for a graphical interface). A program must have a `main` function as its entry point.

A function is a sequence of bindings followed by a return statement. Function names, argument names, and binding names must start with a letter. Binding names must be unique, must not collide with argument names, and a binding may reference only earlier bindings or function arguments in its value expression.

A function starts with the keyword `func`, followed by the function name, followed by a comma-separated list of argument names in parentheses.
After the parentheses, 0 or more symbols from the set `!@#%` may appear. These are function modifiers.
After that comes a sequence of bindings, then the return statement, then the keyword `endfunc`.

A binding is a name, followed by `=`, followed by an expression.
A return statement is the keyword `return`, followed by an expression.

### Expressions

An expression is a constant, a name, or a function call. A call is the function name, followed by argument expressions separated by commas, in parentheses. Calls can be nested.

A call may name a user-defined function, or one of the 4 primitive operations `+`, `-`, `?`, and `≥`. The last one has an alias for ease of typing, `>`.

Call arguments can be binding names, names of arguments in the caller, calls to other functions, or constants.

### Constants

Integer constants are sequences of digits, possibly starting with `-`. The value must lie in `[MIN_INT, MAX_INT]`.

List constants are one of 2: either the empty list `[]`, or a string of characters in double quotes. These characters must be ASCII characters with integer values between 32 and 126. A double quote in a string is written as `\"`. No other escape is recognized: a backslash is a literal character unless it is immediately followed by a double quote. Characters are converted to integers with those values.

Error constants look like a function call named `~` with a single string argument, for example `~("Error message")`. The argument must be a quoted string literal. The error message is that string's text.

### Operations

#### `+`

2 args.

- int, int: sum, clamped into `[MIN_INT, MAX_INT]`.
- int, list/thunk: list/thunk with the int prepended.
- list/thunk, int: list/thunk with the int appended.
- list/thunk, list/thunk: the first with the second appended as an item.
- error, anything; anything, error: the error.
- error, error: an error with their messages combined.

Lists and thunks are limited to `MAX_LIST_LENGTH` items (thunk arguments count as items) and `MAX_LIST_NESTING_DEPTH` nesting. Empty lists and thunks have nesting depth 1. If an operation would produce a list or thunk outside these limits, it is a no-op on the list or thunk being grown: a prepend or append that would exceed a limit returns that sequence unchanged; `list1 + list2` that would exceed a limit returns `list1`.

#### `-`

2 args. Indexes are 0-based.

- int, int: difference, clamped into `[MIN_INT, MAX_INT]`.
- int, list/thunk: the item in the list/thunk at that index. If the index is outside the bounds, it is clamped inside. If the list/thunk has 0 items, the result is the integer argument.
- list/thunk, int: a copy of the list/thunk with the item at that index removed. If the index is outside the bounds, it is clamped inside. If the list/thunk has 0 items, the result is the list/thunk argument.
- list/thunk, list/thunk: a modified copy of the first. Remove the item from the result for every item in the second (list-based, not set-based).
- error, anything; anything, error: the error.
- error, error: an error with their messages combined.

#### `≥`

Alias: `>`.

Comparison of 2 args. Returns 1 if the first item is bigger than or equal to the second. Returns 0 otherwise.

Comparison of 2 integers is by absolute value first; if the absolute values are equal, the negative integer is smaller. Lists are always bigger than ints. Thunks are always bigger than lists. Errors are always bigger than thunks. Comparison of 2 lists or 2 thunks is lexicographical, with the shorter one considered smaller. 2 thunks with different functions are compared by the index of the function in the program.

- error, error: an error with their messages combined.

#### `?`

Choice between 2 args. Returns the value of arg 1 if it is truthy, or returns the value of arg 2 if arg 1 is falsy. Arg 2 is evaluated only when arg 1 is falsy, which is necessary for recursion termination.

- Integer 0 is falsy, and the rest are truthy.
- The empty list is falsy, and the rest are truthy.
- A thunk is always truthy.
- An error is always truthy.

### Function modifiers

#### `!`

Assert wellfoundedness. On entry, after a memoization miss and before a frame is pushed or tail-replaced, compare the new argument list to the nearest live function frame of the same name. If none exists, the call is allowed. If one exists, the new arguments must be strictly smaller, or the call returns an error and does not enter. Other live functions are ignored, so mutual recursion is checked on each function's own re-entry. Integers use the same order as `≥`; lists and thunks use the same lexicographic order as `≥`. Creating a `%` thunk does not check until that thunk is forced. A memoization hit is not checked. Assertion failure outputs an error.

#### `@`

Tail recurse. Reuses the live function frame so a self-call does not increase call depth. Valid only when every self-call is the tail call of the return: the return expression itself, or the lazy branch of a `?` (including nested `?`). Verified at parsing stage.

#### `#`

Memoize. Makes a function remember its input-output pairs, skipping the computation on repeated calls. The table is keyed by function name and the evaluated argument list. A hit returns the stored value without pushing a function frame. A call that has not returned is not a hit. Recursion-depth errors are not stored; other errors are. Functions with both `#` and `%` still produce a thunk at the call site; the table is consulted when that thunk is forced, and stores the unforced body result. Eager functions store the value after a thunk return has been forced. A returned list may still contain thunks.

#### `%`

Output lazily. Makes a function output the thunk of its call. This evaluates the arguments and creates a thunk with the function's name and the list of arguments.

### Evaluation of thunks

Functions without the "output lazily" modifier force a thunk returned as the value itself. Thunk items wrapped inside lists are left unevaluated. The entry point `main` cannot have the "output lazily" modifier. Attempting to evaluate a thunk with the wrong number of arguments outputs an error. Program output cannot be a thunk. When the program result is assigned, values are walked left to right, depth-first: the first error found in lists becomes the result; the first thunk found in lists becomes an error with message `Can't output thunks`. Nested lists are walked; thunk arguments are not.

## Example programs

### Triangular numbers

Unlike the example above, this one uses thunk evaluation to terminate recursion.

```
func main(n)
    return tri(n, 0)
endfunc

func tri(n, acc)%
    done = >(0, n)
    index = -(1, done)
    base = +(acc, [])
    smaller = -(n, 1)
    summed = +(acc, n)
    recur = tri(smaller, summed)
    choices = +(base, recur)
    return -(index, choices)
endfunc
```

### List reversal

```
func main(items)
    return rev(items, [])
endfunc

func rev(items, acc)
    empty = >([], items)
    index = -(1, empty)
    base = +([], acc)
    recur = ?(
        empty, 
        rev(
            -(items, 0), 
            +(-(0, items), acc)
        )
    )
    choices = +(base, recur)
    return -(index, choices)
endfunc
```

### List reversal using tail recursion

```
func main(items)
    wrapped = rev(items, [])
    return -(0, wrapped)
endfunc

func rev(items, acc)@
    empty = >([], items)
    wrapped = +([], acc)
    choices = +(+(0, []), wrapped)
    pick = -(empty, choices)
    last_element = -(0, items)
    items_without_last_elem = -(items, 0)
    acc_with_last_elem = +(last_element, acc)
    return ?(pick, rev(items_without_last_elem, acc_with_last_elem))
endfunc
```

### Multiplication of numbers

```
func main(a, b)
    nonneg = >(b, -(0, b))
    pick = -(1, nonneg)
    pos = ?(pick, times(a, b))
    neg = ?(nonneg, -(0, times(a, -(0, b))))
    choices = +(+(pos, []), neg)
    return -(pick, choices)
endfunc

func times(a, count)
    done = >(0, count)
    smaller = -(count, 1)
    rest = ?(done, +(a, times(a, smaller)))
    return -(rest, done)
endfunc
```

### "Capitalization" of letters in a list

```
func main(items)
    return caps(items)
endfunc

func caps(items)
    empty = >([], items)
    index = -(1, empty)
    base = +([], [])
    recur = ?(
        empty,
        +(
            up(-(0, items)),
            caps(-(items, 0))
        )
    )
    choices = +(base, recur)
    return -(index, choices)
endfunc

func up(n)
    lo = >(n, 97)
    hi = >(122, n)
    islo = >(+(lo, hi), 2)
    upper = -(n, 32)
    pick = -(1, islo)
    choices = +(+(upper, []), n)
    return -(pick, choices)
endfunc
```

### Using arg 1 to "modulate" the values in arg 2

This showcases the power of thunks.

```
func main(mods, data)
    return step(mods, data, [])
endfunc

func step(mods, data, acc)
    empty = >([], mods)
    index = -(1, empty)
    base = +([], acc)
    recur = ?(
        empty,
        step(
            -(mods, 0),
            -(data, 0),
            +(acc, pick(-(0, mods), -(0, data)))
        )
    )
    choices = +(base, recur)
    return -(index, choices)
endfunc

func pick(code, item)
    t0 = keep(item)
    t1 = inc(item)
    t2 = zero(item)
    t3 = blank(item)
    t4 = four(item)
    t5 = wrap(item)
    t6 = nest(item)
    c0 = +([], t0)
    c1 = +(c0, t1)
    c2 = +(c1, t2)
    c3 = +(c2, t3)
    c4 = +(c3, t4)
    c5 = +(c4, t5)
    c6 = +(c5, t6)
    return -(code, c6)
endfunc

func keep(item)%
    return item
endfunc

func inc(item)%
    return +(item, 1)
endfunc

func zero(item)%
    return 0
endfunc

func blank(item)%
    return []
endfunc

func four(item)%
    return "FOUR"
endfunc

func wrap(item)%
    return +(item, [])
endfunc

func nest(item)%
    return +([], +(item, []))
endfunc
```

### Fibonacci

This showcases the speedup from memoization.

```
func main(n)
    return fib(n)
endfunc

func fib(n)#
    done = >(1, n)
    n1 = -(n, 1)
    n2 = -(n, 2)
    rec = ?(done, +(fib(n1), fib(n2)))
    pick = -(1, done)
    choices = +(+(n, []), rec)
    return -(pick, choices)
endfunc
```

### Greatest common divisor

Each recursive pair is strictly smaller in the order `!` checks.

```
func main(a, b)
    return gcd(a, b)
endfunc

func gcd(a, b)!
    azero = >(0, a)
    bzero = >(0, b)
    done = >(+(azero, bzero), 1)
    kept_index = -(1, azero)
    kept_choices = +(+(b, []), a)
    kept = -(kept_index, kept_choices)
    base = +(kept, [])
    index = -(1, done)
    ageb = >(a, b)
    diff_a = -(a, b)
    diff_b = -(b, a)
    a_choices = +(+(a, []), diff_a)
    b_choices = +(+(diff_b, []), b)
    next_a = -(ageb, a_choices)
    next_b = -(ageb, b_choices)
    recur = ?(done, gcd(next_a, next_b))
    choices = +(base, recur)
    return -(index, choices)
endfunc
```
