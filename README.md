RRE: Functional esolang. Planned for an eventual graphical syntax and gamefication.

Example program. It computes the Nth triangular number:
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

Specification:

There are 4 types: int and list and thunk and error.
Integers can be negative.
Lists are immutable and can hold both ints and other lists and thunks.
Thunks are like lists, containing values of arguments, and metadata for the function to apply.
Errors carry error messages. Errors infect every operation, forcing it to output error when evaluated. The exceptions are an operation with 2 errors, where they're combined to propagate the error messages, and the ? operator, which leaves the second arg unevaluated until needed.

Programs are defined as sequences of functions. Functions must have different names, start with different letters (reserved for a graphical interface), and have a main function as an entry point.
Functions are defined as sequences of binding expressions, followed by a return statement. Function names, argument names, and binding names must start with a letter. Binding names must be unique, not collide with argument names, and any binding can only reference earlier bindings or function arguments in its value expression.

A function starts with the keyword func, followed by the name of the function, followed by argument name list separated by commas in parentheses.
After parentheses can go 0 or more symbols from the set `!@#%`. These are function modifiers.
After this goes a sequence of binding definitions, then the return statement, then the endfunc keyword.

Bindings look like a binding name, followed by the = sign, followed by the binding expression.
Return statement looks like the `return` keyword, followed by an expression.
Every expression consists of function calls. A function call looks like the function name, followed by the list of argument expressions, separated by commas, in parentheses. Function calls can be composed in one expression. 

Functions can be either user-defined functions, referenced by their names, or the 4 primitive operation functions, `+-?≥`, referenced by their symbols. The last one has an alias for ease of typing, `>`.

Function call arguments can be binding names, names of arguments in the caller function, calls to other functions, or constants.

Integer constants are sequences of digits, or a `-` immediately followed by digits with no space. The value must lie in `[MIN_INT, MAX_INT]`. 
List constants are one of 2: either the empty list constant `[]`, or a string of characters in "quotes". These characters must be ASCII characters with integer values between 32 and 126. A `"` in a string is written as `\"`. No other escape is recognized: a backslash is a literal character unless it is immediately followed by `"`. Characters are converted to integers with those values.
Error constants look like a function call named `~` with a single string argument, for example `~("Error message")`. The argument must be a quoted string literal. The error message is that string's text.

Return values for operation functions:

+: 2 args.
int, int: sum, clamped into [MIN_INT, MAX_INT]
int, list/thunk: list/thunk with int prepended
list/thunk, int: list/thunk with int appended
list/thunk1, list/thunk2: list/thunk1 with list/thunk2 appended as an item
Lists and thunks are limited to MAX_LIST_LENGTH items (thunk arguments count as items) and MAX_LIST_NESTING_DEPTH nesting. Empty lists and thunks have nesting depth 1. If an operation would produce a list or thunk outside these limits, it is a noop on the list or thunk being grown: prepend/append that would exceed returns that sequence unchanged; list1 + list2 that would exceed returns list1.
error, anything; anything, error: the error
error, error: error with their messages combined


Indexes are 0-based.
-: 2 args.
int, int: difference, clamped into [MIN_INT, MAX_INT]
int, list/thunk: retrieval of item in list/thunk at idx int. If int is outside the bounds of list/thunk, it is clamped inside. If list/thunk has 0 items, output the int.
list/thunk, int: copying of list/thunk with item at int idx removed. If int is outside the bounds of list/thunk, it is clamped inside. If list/thunk has 0 items, the output is list/thunk.
list/thunk1, list/thunk2: return a modified copy of list/thunk1. Remove the item from the result for every item in list/thunk2. (List-based, not set-based)
error, anything; anything, error: the error
error, error: error with their messages combined

≥: comparison of 2 args. Return 1 if item 1 is bigger than or equal to item 2. Return 0 otherwise.
Comparison of 2 integers is by absolute value first; if the absolute values are equal, the negative integer is smaller. Lists are always bigger than ints. Thunks are always bigger than lists. Errors are always bigger than thunks. Comparison of 2 lists or 2 thunks is lexicographical, with shorter lists considered smaller. 2 thunks with different functions are compared by the index of the function in the program.
error, error: error with their messages combined

?: choice between 2 args. Returns the value of arg1 if it is "truthy", or return the value of arg2 if arg1 is "falsy". Arg 2 is evaluated lazily unless arg1 is truthy, which is necessary for recursion termination. 
Integer 0 is falsy, and the rest are truthy. Empty list is falsy, and the rest are truthy. Thunk is always truthy. Error is always truthy.

Function modifiers:

!: assert wellfoundedness. On entry, after a memoization miss and before a frame is pushed or tail-replaced, compare the new argument list to the nearest live function frame of the same name. If none exists, the call is allowed. If one exists, the new arguments must be strictly smaller, or the call returns an error and does not enter. Other live functions are ignored, so mutual recursion is checked on each function's own re-entry. Integers use the same order as ≥; lists and thunks use the same lexicographic order as ≥. Creating a % thunk does not check until that thunk is forced. A memoization hit is not checked. Assertion failure outputs an error.
@: tail recurse, reuses the live function frame so a self-call does not increase call depth. Valid only when every self-call is the tail call of the return: the return expression itself, or the lazy branch of a `?` (including nested `?`). Verified at parsing stage.
#: memoize, makes a function remember the IO pairs, skipping the computation on repeated calls. The table is keyed by function name and the evaluated argument list. A hit returns the stored value without pushing a function frame. A call that has not returned is not a hit. Recursion-depth errors are not stored; other errors are. Functions with both # and % still produce a thunk at the call site; the table is consulted when that thunk is forced, and stores the unforced body result. Eager functions store the value after a thunk return has been forced. A returned list may still contain thunks.
%: output lazily, makes a function output the thunk of its call. This evaluates values of arguments to the call and creates a thunk with the function's name and list of arguments.

Evaluation of thunks:
Functions without the "output lazily" modifier force a thunk returned as the value itself. Thunk items wrapped inside lists are left unevaluated. Entry point "main" cannot have the "output lazily" modifier. Attempting to evaluate a thunk with a wrong number of arguments outputs an error. Program output cannot be a thunk. When the program result is assigned, values are walked left to right, depth-first: the first error found in lists becomes the result; the first thunk found in lists becomes an error with message "Can't output thunks". Nested lists are walked; thunk arguments are not.

Example programs:

Triangular numbers. Unlike the shown example, it uses thunk evaluation to terminate recursion.
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

List reversal:
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

List reversal using tail recursion:
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

Multiplication of numbers:
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

"Capitalization" of letters in a list:
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

Using arg 1 to "modulate" the values in arg 2. This showcases the power of thunks.
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