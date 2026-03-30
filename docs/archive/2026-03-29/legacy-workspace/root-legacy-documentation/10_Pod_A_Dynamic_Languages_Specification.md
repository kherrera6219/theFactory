# POD A: DYNAMIC LANGUAGES SPECIFICATION
## Complete Domain Catalog for Python, JavaScript, Ruby, PHP

**Version:** 1.0  
**Date:** February 2026  
**Status:** Design Phase - Complete Specification  
**Document Owner:** Pod A Sub-Manager

---

## EXECUTIVE SUMMARY

Pod A handles the four major dynamic programming languages: Python, JavaScript, Ruby, and PHP. These languages share common characteristics: dynamic typing, first-class functions, flexible syntax, and emphasis on developer productivity over compile-time guarantees. This document provides the complete domain registry, concept catalog, and language mappings for all concepts that these four languages express.

**Pod A Languages:**
- **Python** - General-purpose scripting, data science, web backends
- **JavaScript** - Web frontends, Node.js backends, full-stack development
- **Ruby** - Web applications (Rails), elegant scripting, DSLs
- **PHP** - Web backends, WordPress, server-side rendering

---

## 1. POD A PARADIGM CHARACTERISTICS

### 1.1 Shared Characteristics

All four languages in Pod A share:

1. **Dynamic Typing** - Types checked at runtime, not compile time
2. **Duck Typing** - "If it walks like a duck and quacks like a duck, it's a duck"
3. **First-Class Functions** - Functions as values, closures, callbacks
4. **Garbage Collection** - Automatic memory management
5. **Interpreted Execution** - No compilation step required
6. **Flexible Syntax** - Multiple ways to express the same concept
7. **REPL Support** - Interactive development environments
8. **Rich Standard Libraries** - Batteries included philosophy

### 1.2 Key Differences

| Aspect | Python | JavaScript | Ruby | PHP |
|--------|--------|------------|------|-----|
| **Primary Use** | General-purpose, data science | Web, full-stack | Web, scripting | Web backends |
| **Typing** | Dynamic, optional type hints | Dynamic, TypeScript adds types | Dynamic | Dynamic, type declarations in 7.4+ |
| **Async Model** | async/await | Promises, async/await | Fibers (experimental) | Promises in 8.1+ |
| **OOP Style** | Class-based | Prototype + class syntax | Class-based, mixins | Class-based |
| **Indentation** | Significant | Curly braces | end keyword | Curly braces |

---

## 2. DOMAIN REGISTRY

Pod A handles 18 domains:

| Domain ID | Domain Name | Concept Count | Description |
|-----------|-------------|---------------|-------------|
| **DYN-001** | List Operations | 12 | Array/list manipulation and transformation |
| **DYN-002** | String Manipulation | 10 | Text processing and formatting |
| **DYN-003** | Dictionary Operations | 8 | Key-value data structures |
| **DYN-004** | Control Flow | 6 | Conditionals and loops |
| **DYN-005** | Function Patterns | 8 | Higher-order functions and closures |
| **DYN-006** | Async Patterns | 5 | Asynchronous programming |
| **DYN-007** | Error Handling | 4 | Exception management |
| **DYN-008** | IO Operations | 6 | File and stream operations |
| **DYN-009** | HTTP Operations | 8 | Web requests and responses |
| **DYN-010** | Serialization | 6 | Data format conversion |
| **DYN-011** | Type Coercion | 5 | Dynamic type conversion |
| **DYN-012** | Iteration Patterns | 6 | Advanced iteration techniques |
| **DYN-013** | Module Patterns | 4 | Code organization |
| **DYN-014** | Object Patterns | 8 | Object-oriented programming |
| **DYN-015** | DOM Manipulation | 6 | Browser DOM interaction (JS-heavy) |
| **DYN-016** | DateTime Operations | 6 | Date and time handling |
| **DYN-017** | Regex Patterns | 4 | Regular expressions |
| **DYN-018** | Environment Config | 4 | Configuration and environment variables |
| **Total** | | **106** | |

---

## 3. COMPLETE CONCEPT CATALOG

### DOMAIN: DYN-001 (List Operations)

#### Concept: filter_collection
**Intent:** Return elements that satisfy a predicate  
**Concept ID:** DYN-001-001

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `filter(fn, list)` or `[x for x in list if fn(x)]` | Built-in or comprehension |
| JavaScript | `array.filter(fn)` | Array method |
| Ruby | `array.select { \|x\| fn(x) }` | Enumerable method |
| PHP | `array_filter($array, $fn)` | Built-in function |

**LogicNode Template:**
```json
{
  "domain": "list_operations",
  "concept": "filter_collection",
  "intent": "Return elements that satisfy a predicate",
  "inputs": [
    {"name": "source", "type": {"base": "list"}},
    {"name": "predicate", "type": {"base": "function"}}
  ],
  "outputs": [
    {"name": "result", "type": {"base": "list"}}
  ],
  "preconditions": [],
  "postconditions": [
    {"type": "predicate", "expression": "forall(x in result): predicate(x)"}
  ],
  "side_effects": []
}
```

---

#### Concept: map_collection
**Intent:** Transform each element  
**Concept ID:** DYN-001-002

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `map(fn, list)` or `[fn(x) for x in list]` | |
| JavaScript | `array.map(fn)` | |
| Ruby | `array.map { \|x\| fn(x) }` | |
| PHP | `array_map($fn, $array)` | |

---

#### Concept: reduce_collection
**Intent:** Accumulate values into single result  
**Concept ID:** DYN-001-003

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `functools.reduce(fn, list, initial)` | |
| JavaScript | `array.reduce(fn, initial)` | |
| Ruby | `array.reduce(initial) { \|acc, x\| fn(acc, x) }` | |
| PHP | `array_reduce($array, $fn, $initial)` | |

---

#### Concept: sort_collection
**Intent:** Order elements  
**Concept ID:** DYN-001-004

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `sorted(list)` or `list.sort()` | Immutable vs mutable |
| JavaScript | `array.sort(compareFn)` | Mutable, in-place |
| Ruby | `array.sort` or `array.sort_by { \|x\| key }` | |
| PHP | `sort($array)` or `usort($array, $fn)` | |

---

#### Concept: find_element
**Intent:** Return first element matching predicate  
**Concept ID:** DYN-001-005

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `next((x for x in list if pred(x)), None)` | |
| JavaScript | `array.find(pred)` | |
| Ruby | `array.find { \|x\| pred(x) }` | |
| PHP | Custom loop or `array_filter` first element | No built-in |

---

#### Concept: flatten_collection
**Intent:** Convert nested lists to single-level list  
**Concept ID:** DYN-001-006

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `itertools.chain(*list)` or list comprehension | |
| JavaScript | `array.flat(depth)` | |
| Ruby | `array.flatten(depth)` | |
| PHP | Custom recursion or `array_merge` | |

---

#### Concept: unique_elements
**Intent:** Remove duplicates  
**Concept ID:** DYN-001-007

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `list(set(array))` | Order not preserved |
| JavaScript | `[...new Set(array)]` | |
| Ruby | `array.uniq` | |
| PHP | `array_unique($array)` | |

---

#### Concept: slice_collection
**Intent:** Extract sub-range  
**Concept ID:** DYN-001-008

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `list[start:end]` | |
| JavaScript | `array.slice(start, end)` | |
| Ruby | `array[start..end]` or `array.slice(start, length)` | |
| PHP | `array_slice($array, $start, $length)` | |

---

#### Concept: concat_collections
**Intent:** Combine multiple lists  
**Concept ID:** DYN-001-009

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `list1 + list2` or `[*list1, *list2]` | |
| JavaScript | `array1.concat(array2)` or `[...array1, ...array2]` | |
| Ruby | `array1 + array2` or `array1.concat(array2)` | |
| PHP | `array_merge($array1, $array2)` | |

---

#### Concept: reverse_collection
**Intent:** Reverse order of elements  
**Concept ID:** DYN-001-010

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `reversed(list)` or `list[::-1]` | |
| JavaScript | `array.reverse()` | Mutable |
| Ruby | `array.reverse` | |
| PHP | `array_reverse($array)` | |

---

#### Concept: partition_collection
**Intent:** Split into two groups based on predicate  
**Concept ID:** DYN-001-011

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `(filter(pred, lst), filter(lambda x: not pred(x), lst))` | |
| JavaScript | Manual implementation | |
| Ruby | `array.partition { \|x\| pred(x) }` | |
| PHP | Manual implementation | |

---

#### Concept: zip_collections
**Intent:** Combine elements from multiple lists pairwise  
**Concept ID:** DYN-001-012

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `zip(list1, list2)` | |
| JavaScript | `list1.map((v, i) => [v, list2[i]])` | |
| Ruby | `list1.zip(list2)` | |
| PHP | `array_map(null, $list1, $list2)` | |

---

### DOMAIN: DYN-002 (String Manipulation)

#### Concept: concat_strings
**Intent:** Join strings  
**Concept ID:** DYN-002-001

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `str1 + str2` or `f"{str1}{str2}"` | |
| JavaScript | `str1 + str2` or `` `${str1}${str2}` `` | |
| Ruby | `str1 + str2` or `"#{str1}#{str2}"` | |
| PHP | `$str1 . $str2` | |

---

#### Concept: split_string
**Intent:** Break string into parts  
**Concept ID:** DYN-002-002

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `str.split(delim)` | |
| JavaScript | `str.split(delim)` | |
| Ruby | `str.split(delim)` | |
| PHP | `explode($delim, $str)` | |

---

#### Concept: join_strings
**Intent:** Combine list of strings with delimiter  
**Concept ID:** DYN-002-003

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `delim.join(list)` | |
| JavaScript | `array.join(delim)` | |
| Ruby | `array.join(delim)` | |
| PHP | `implode($delim, $array)` | |

---

#### Concept: substring
**Intent:** Extract portion of string  
**Concept ID:** DYN-002-004

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `str[start:end]` | |
| JavaScript | `str.substring(start, end)` or `str.slice(start, end)` | |
| Ruby | `str[start..end]` or `str.slice(start, length)` | |
| PHP | `substr($str, $start, $length)` | |

---

#### Concept: trim_string
**Intent:** Remove whitespace from ends  
**Concept ID:** DYN-002-005

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `str.strip()` | |
| JavaScript | `str.trim()` | |
| Ruby | `str.strip` | |
| PHP | `trim($str)` | |

---

#### Concept: replace_substring
**Intent:** Replace occurrences  
**Concept ID:** DYN-002-006

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `str.replace(old, new)` | |
| JavaScript | `str.replace(old, new)` or `str.replaceAll(old, new)` | |
| Ruby | `str.gsub(old, new)` | |
| PHP | `str_replace($old, $new, $str)` | |

---

#### Concept: to_uppercase
**Intent:** Convert to uppercase  
**Concept ID:** DYN-002-007

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `str.upper()` | |
| JavaScript | `str.toUpperCase()` | |
| Ruby | `str.upcase` | |
| PHP | `strtoupper($str)` | |

---

#### Concept: to_lowercase
**Intent:** Convert to lowercase  
**Concept ID:** DYN-002-008

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `str.lower()` | |
| JavaScript | `str.toLowerCase()` | |
| Ruby | `str.downcase` | |
| PHP | `strtolower($str)` | |

---

#### Concept: starts_with
**Intent:** Check prefix  
**Concept ID:** DYN-002-009

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `str.startswith(prefix)` | |
| JavaScript | `str.startsWith(prefix)` | |
| Ruby | `str.start_with?(prefix)` | |
| PHP | `str_starts_with($str, $prefix)` | PHP 8+ |

---

#### Concept: ends_with
**Intent:** Check suffix  
**Concept ID:** DYN-002-010

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `str.endswith(suffix)` | |
| JavaScript | `str.endsWith(suffix)` | |
| Ruby | `str.end_with?(suffix)` | |
| PHP | `str_ends_with($str, $suffix)` | PHP 8+ |

---

### DOMAIN: DYN-003 (Dictionary Operations)

#### Concept: get_value
**Intent:** Retrieve value by key  
**Concept ID:** DYN-003-001

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `dict[key]` or `dict.get(key, default)` | |
| JavaScript | `obj[key]` or `obj.key` | |
| Ruby | `hash[key]` or `hash.fetch(key, default)` | |
| PHP | `$array[$key]` or `$array[$key] ?? $default` | |

---

#### Concept: set_value
**Intent:** Store value by key  
**Concept ID:** DYN-003-002

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `dict[key] = value` | |
| JavaScript | `obj[key] = value` | |
| Ruby | `hash[key] = value` | |
| PHP | `$array[$key] = $value` | |

---

#### Concept: delete_key
**Intent:** Remove key-value pair  
**Concept ID:** DYN-003-003

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `del dict[key]` or `dict.pop(key)` | |
| JavaScript | `delete obj[key]` | |
| Ruby | `hash.delete(key)` | |
| PHP | `unset($array[$key])` | |

---

#### Concept: has_key
**Intent:** Check key existence  
**Concept ID:** DYN-003-004

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `key in dict` | |
| JavaScript | `key in obj` or `obj.hasOwnProperty(key)` | |
| Ruby | `hash.key?(key)` or `hash.has_key?(key)` | |
| PHP | `array_key_exists($key, $array)` or `isset($array[$key])` | |

---

#### Concept: keys
**Intent:** Get all keys  
**Concept ID:** DYN-003-005

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `dict.keys()` or `list(dict.keys())` | |
| JavaScript | `Object.keys(obj)` | |
| Ruby | `hash.keys` | |
| PHP | `array_keys($array)` | |

---

#### Concept: values
**Intent:** Get all values  
**Concept ID:** DYN-003-006

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `dict.values()` or `list(dict.values())` | |
| JavaScript | `Object.values(obj)` | |
| Ruby | `hash.values` | |
| PHP | `array_values($array)` | |

---

#### Concept: items
**Intent:** Get key-value pairs  
**Concept ID:** DYN-003-007

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `dict.items()` | |
| JavaScript | `Object.entries(obj)` | |
| Ruby | `hash.to_a` or iteration | |
| PHP | Foreach iteration | |

---

#### Concept: merge_dicts
**Intent:** Combine dictionaries  
**Concept ID:** DYN-003-008

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `{**dict1, **dict2}` or `dict1 \| dict2` (3.9+) | |
| JavaScript | `{...obj1, ...obj2}` or `Object.assign({}, obj1, obj2)` | |
| Ruby | `hash1.merge(hash2)` | |
| PHP | `array_merge($array1, $array2)` | |

---

### DOMAIN: DYN-004 (Control Flow)

#### Concept: if_condition
**Intent:** Conditional execution  
**Concept ID:** DYN-004-001

**Universal pattern across all 4 languages**

---

#### Concept: while_loop
**Intent:** Repeat while condition true  
**Concept ID:** DYN-004-002

**Universal pattern across all 4 languages**

---

#### Concept: for_loop
**Intent:** Iterate over collection  
**Concept ID:** DYN-004-003

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `for item in collection:` | |
| JavaScript | `for (const item of collection)` | |
| Ruby | `collection.each { \|item\| ... }` or `for item in collection` | |
| PHP | `foreach ($collection as $item)` | |

---

#### Concept: break_loop
**Intent:** Exit loop early  
**Concept ID:** DYN-004-004

**Universal pattern across all 4 languages**

---

#### Concept: continue_loop
**Intent:** Skip to next iteration  
**Concept ID:** DYN-004-005

**Universal pattern across all 4 languages**

---

#### Concept: switch_case
**Intent:** Multi-way branching  
**Concept ID:** DYN-004-006

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `match/case` (3.10+) or if/elif/else | |
| JavaScript | `switch (value) { case x: ... }` | |
| Ruby | `case value when x then ... end` | |
| PHP | `switch ($value) { case $x: ... }` | |

---

### DOMAIN: DYN-005 (Function Patterns)

#### Concept: define_function
**Intent:** Create named function  
**Concept ID:** DYN-005-001

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `def name(args): ...` | |
| JavaScript | `function name(args) {}` or `const name = (args) => {}` | |
| Ruby | `def name(args) ... end` | |
| PHP | `function name($args) {}` | |

---

#### Concept: anonymous_function
**Intent:** Create unnamed function  
**Concept ID:** DYN-005-002

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `lambda args: expr` | |
| JavaScript | `(args) => expr` or `function(args) {}` | |
| Ruby | `lambda { \|args\| expr }` or `-> (args) { expr }` | |
| PHP | `function($args) {}` or `fn($args) => expr` (7.4+) | |

---

#### Concept: closure
**Intent:** Function capturing outer scope  
**Concept ID:** DYN-005-003

**All 4 languages support closures naturally**

---

#### Concept: partial_application
**Intent:** Fix some arguments  
**Concept ID:** DYN-005-004

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `functools.partial(fn, arg1)` | |
| JavaScript | `fn.bind(null, arg1)` or manual wrapper | |
| Ruby | `fn.curry[arg1]` | |
| PHP | Manual wrapper function | |

---

#### Concept: default_parameters
**Intent:** Provide default values  
**Concept ID:** DYN-005-005

**Universal pattern across all 4 languages**

---

#### Concept: variadic_arguments
**Intent:** Accept variable number of arguments  
**Concept ID:** DYN-005-006

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `def fn(*args, **kwargs)` | |
| JavaScript | `function fn(...args)` | |
| Ruby | `def fn(*args)` | |
| PHP | `function fn(...$args)` | |

---

#### Concept: function_composition
**Intent:** Combine functions  
**Concept ID:** DYN-005-007

**Manual implementation in all languages**

---

#### Concept: callback
**Intent:** Pass function as argument  
**Concept ID:** DYN-005-008

**First-class functions in all 4 languages**

---

### DOMAIN: DYN-006 (Async Patterns)

#### Concept: async_function
**Intent:** Define asynchronous function  
**Concept ID:** DYN-006-001

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `async def fn():` | |
| JavaScript | `async function fn()` | |
| Ruby | Experimental Fibers | Not standard |
| PHP | ReactPHP or Amp libraries | Not native in < 8.1 |

---

#### Concept: await_result
**Intent:** Wait for async operation  
**Concept ID:** DYN-006-002

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `await fn()` | |
| JavaScript | `await fn()` | |
| Ruby | Fiber-based | |
| PHP | Library-specific | |

---

#### Concept: create_promise
**Intent:** Create async promise  
**Concept ID:** DYN-006-003

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `asyncio.Future` or `asyncio.Task` | |
| JavaScript | `new Promise((resolve, reject) => {})` | |
| Ruby | N/A | |
| PHP | Libraries like ReactPHP | |

---

#### Concept: parallel_all
**Intent:** Wait for multiple async operations  
**Concept ID:** DYN-006-004

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `asyncio.gather(*tasks)` | |
| JavaScript | `Promise.all(promises)` | |
| Ruby | N/A | |
| PHP | Library-specific | |

---

#### Concept: timeout
**Intent:** Limit async operation time  
**Concept ID:** DYN-006-005

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `asyncio.wait_for(coro, timeout)` | |
| JavaScript | `Promise.race([promise, timeoutPromise])` | |
| Ruby | `Timeout.timeout(seconds)` | |
| PHP | Library-specific | |

---

### DOMAIN: DYN-007 (Error Handling)

#### Concept: try_catch
**Intent:** Handle exceptions  
**Concept ID:** DYN-007-001

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `try: ... except Exception as e: ...` | |
| JavaScript | `try {} catch (e) {}` | |
| Ruby | `begin ... rescue => e ... end` | |
| PHP | `try {} catch (Exception $e) {}` | |

---

#### Concept: throw_error
**Intent:** Raise exception  
**Concept ID:** DYN-007-002

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `raise Exception("msg")` | |
| JavaScript | `throw new Error("msg")` | |
| Ruby | `raise "msg"` or `raise StandardError, "msg"` | |
| PHP | `throw new Exception("msg")` | |

---

#### Concept: finally_block
**Intent:** Always execute code  
**Concept ID:** DYN-007-003

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `try: ... finally: ...` | |
| JavaScript | `try {} finally {}` | |
| Ruby | `begin ... ensure ... end` | |
| PHP | `try {} finally {}` | |

---

#### Concept: custom_exception
**Intent:** Define exception class  
**Concept ID:** DYN-007-004

**All 4 languages support custom exception classes**

---

### DOMAIN: DYN-008 (IO Operations)

#### Concept: read_file
**Intent:** Load file contents  
**Concept ID:** DYN-008-001

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `open(path).read()` or `pathlib.Path(path).read_text()` | |
| JavaScript | `fs.readFileSync(path)` (Node.js) | |
| Ruby | `File.read(path)` | |
| PHP | `file_get_contents($path)` | |

---

#### Concept: write_file
**Intent:** Save file contents  
**Concept ID:** DYN-008-002

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `open(path, 'w').write(data)` | |
| JavaScript | `fs.writeFileSync(path, data)` | |
| Ruby | `File.write(path, data)` | |
| PHP | `file_put_contents($path, $data)` | |

---

#### Concept: append_file
**Intent:** Add to file  
**Concept ID:** DYN-008-003

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `open(path, 'a').write(data)` | |
| JavaScript | `fs.appendFileSync(path, data)` | |
| Ruby | `File.open(path, 'a') { \|f\| f.write(data) }` | |
| PHP | `file_put_contents($path, $data, FILE_APPEND)` | |

---

#### Concept: delete_file
**Intent:** Remove file  
**Concept ID:** DYN-008-004

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `os.remove(path)` or `pathlib.Path(path).unlink()` | |
| JavaScript | `fs.unlinkSync(path)` | |
| Ruby | `File.delete(path)` | |
| PHP | `unlink($path)` | |

---

#### Concept: file_exists
**Intent:** Check file existence  
**Concept ID:** DYN-008-005

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `os.path.exists(path)` or `pathlib.Path(path).exists()` | |
| JavaScript | `fs.existsSync(path)` | |
| Ruby | `File.exist?(path)` | |
| PHP | `file_exists($path)` | |

---

#### Concept: list_directory
**Intent:** Get directory contents  
**Concept ID:** DYN-008-006

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `os.listdir(path)` or `pathlib.Path(path).iterdir()` | |
| JavaScript | `fs.readdirSync(path)` | |
| Ruby | `Dir.entries(path)` | |
| PHP | `scandir($path)` | |

---

### DOMAIN: DYN-009 (HTTP Operations)

#### Concept: http_get
**Intent:** Make GET request  
**Concept ID:** DYN-009-001

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `requests.get(url)` or `urllib` | |
| JavaScript | `fetch(url)` or `axios.get(url)` | |
| Ruby | `Net::HTTP.get(uri)` or RestClient | |
| PHP | `file_get_contents($url)` or cURL | |

---

#### Concept: http_post
**Intent:** Make POST request  
**Concept ID:** DYN-009-002

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `requests.post(url, data=data)` | |
| JavaScript | `fetch(url, {method: 'POST', body: data})` | |
| Ruby | `Net::HTTP.post(uri, data)` | |
| PHP | `curl_exec()` with POST | |

---

#### Concept: set_headers
**Intent:** Add HTTP headers  
**Concept ID:** DYN-009-003

**Pattern available in all languages' HTTP libraries**

---

#### Concept: parse_response
**Intent:** Extract response data  
**Concept ID:** DYN-009-004

**Pattern available in all languages' HTTP libraries**

---

#### Concept: handle_status
**Intent:** Check response code  
**Concept ID:** DYN-009-005

**Pattern available in all languages' HTTP libraries**

---

#### Concept: set_timeout
**Intent:** Limit request time  
**Concept ID:** DYN-009-006

**Pattern available in all languages' HTTP libraries**

---

#### Concept: follow_redirects
**Intent:** Handle 3xx responses  
**Concept ID:** DYN-009-007

**Pattern available in all languages' HTTP libraries**

---

#### Concept: send_json
**Intent:** POST JSON data  
**Concept ID:** DYN-009-008

**Pattern available in all languages' HTTP libraries**

---

### DOMAIN: DYN-010 (Serialization)

#### Concept: json_encode
**Intent:** Convert to JSON string  
**Concept ID:** DYN-010-001

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `json.dumps(data)` | |
| JavaScript | `JSON.stringify(data)` | |
| Ruby | `data.to_json` | |
| PHP | `json_encode($data)` | |

---

#### Concept: json_decode
**Intent:** Parse JSON string  
**Concept ID:** DYN-010-002

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `json.loads(string)` | |
| JavaScript | `JSON.parse(string)` | |
| Ruby | `JSON.parse(string)` | |
| PHP | `json_decode($string, true)` | |

---

#### Concept: csv_parse
**Intent:** Parse CSV data  
**Concept ID:** DYN-010-003

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `csv.reader(data)` | |
| JavaScript | PapaParse library | |
| Ruby | `CSV.parse(data)` | |
| PHP | `str_getcsv($line)` | |

---

#### Concept: csv_generate
**Intent:** Create CSV string  
**Concept ID:** DYN-010-004

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `csv.writer(output).writerows(data)` | |
| JavaScript | PapaParse library | |
| Ruby | `CSV.generate { \|csv\| ... }` | |
| PHP | `fputcsv()` | |

---

#### Concept: xml_parse
**Intent:** Parse XML  
**Concept ID:** DYN-010-005

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `xml.etree.ElementTree.fromstring(xml)` | |
| JavaScript | `new DOMParser().parseFromString(xml, 'text/xml')` | |
| Ruby | `Nokogiri::XML(xml)` | |
| PHP | `simplexml_load_string($xml)` | |

---

#### Concept: yaml_parse
**Intent:** Parse YAML  
**Concept ID:** DYN-010-006

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `yaml.safe_load(string)` | |
| JavaScript | js-yaml library | |
| Ruby | `YAML.load(string)` | |
| PHP | `yaml_parse($string)` | Requires extension |

---

### DOMAIN: DYN-011 (Type Coercion)

#### Concept: to_string
**Intent:** Convert to string  
**Concept ID:** DYN-011-001

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `str(value)` | |
| JavaScript | `String(value)` or `value.toString()` | |
| Ruby | `value.to_s` | |
| PHP | `(string)$value` or `strval($value)` | |

---

#### Concept: to_integer
**Intent:** Convert to integer  
**Concept ID:** DYN-011-002

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `int(value)` | |
| JavaScript | `parseInt(value)` or `Number(value)` | |
| Ruby | `value.to_i` | |
| PHP | `(int)$value` or `intval($value)` | |

---

#### Concept: to_float
**Intent:** Convert to float  
**Concept ID:** DYN-011-003

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `float(value)` | |
| JavaScript | `parseFloat(value)` | |
| Ruby | `value.to_f` | |
| PHP | `(float)$value` or `floatval($value)` | |

---

#### Concept: to_boolean
**Intent:** Convert to boolean  
**Concept ID:** DYN-011-004

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `bool(value)` | |
| JavaScript | `Boolean(value)` | |
| Ruby | `!!value` | |
| PHP | `(bool)$value` | |

---

#### Concept: type_check
**Intent:** Check value type  
**Concept ID:** DYN-011-005

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `type(value)` or `isinstance(value, Type)` | |
| JavaScript | `typeof value` or `value instanceof Type` | |
| Ruby | `value.class` or `value.is_a?(Type)` | |
| PHP | `gettype($value)` or `is_int($value)` | |

---

### DOMAIN: DYN-012 (Iteration Patterns)

#### Concept: enumerate
**Intent:** Iterate with index  
**Concept ID:** DYN-012-001

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `enumerate(iterable)` | |
| JavaScript | `array.forEach((item, index) => {})` | |
| Ruby | `array.each_with_index { \|item, i\| }` | |
| PHP | `foreach ($array as $i => $value)` | |

---

#### Concept: range
**Intent:** Generate number sequence  
**Concept ID:** DYN-012-002

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `range(start, end, step)` | |
| JavaScript | `Array.from({length: n}, (_, i) => i)` | |
| Ruby | `(start..end)` or `(start...end)` | |
| PHP | `range($start, $end, $step)` | |

---

#### Concept: generator
**Intent:** Lazy iteration  
**Concept ID:** DYN-012-003

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `yield` in function | |
| JavaScript | `function* gen() { yield ... }` | |
| Ruby | `Enumerator` or Fiber | |
| PHP | `yield` in function (5.5+) | |

---

#### Concept: comprehension
**Intent:** Transform with inline expression  
**Concept ID:** DYN-012-004

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `[expr for x in iterable if cond]` | |
| JavaScript | `array.map().filter()` chaining | |
| Ruby | `array.map { \|x\| expr }.select { \|x\| cond }` | |
| PHP | `array_map()` and `array_filter()` | |

---

#### Concept: chunk
**Intent:** Split into fixed-size groups  
**Concept ID:** DYN-012-005

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `[lst[i:i+n] for i in range(0, len(lst), n)]` | |
| JavaScript | Manual implementation | |
| Ruby | `array.each_slice(n)` | |
| PHP | `array_chunk($array, $size)` | |

---

#### Concept: cycle
**Intent:** Repeat sequence infinitely  
**Concept ID:** DYN-012-006

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `itertools.cycle(iterable)` | |
| JavaScript | Manual implementation | |
| Ruby | `array.cycle` | |
| PHP | Manual implementation | |

---

### DOMAIN: DYN-013 (Module Patterns)

#### Concept: import_module
**Intent:** Load external module  
**Concept ID:** DYN-013-001

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `import module` or `from module import item` | |
| JavaScript | `import module from 'path'` or `require('path')` | |
| Ruby | `require 'module'` | |
| PHP | `require 'path'` or `use Namespace\Class` | |

---

#### Concept: export_item
**Intent:** Make available for import  
**Concept ID:** DYN-013-002

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `__all__ = ['item']` (convention) | |
| JavaScript | `export { item }` or `export default item` | |
| Ruby | Module inclusion | |
| PHP | Class/function visibility | |

---

#### Concept: define_namespace
**Intent:** Create named scope  
**Concept ID:** DYN-013-003

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | Modules/packages | |
| JavaScript | Modules or object namespaces | |
| Ruby | `module Namespace ... end` | |
| PHP | `namespace Namespace;` | |

---

#### Concept: relative_import
**Intent:** Import from relative path  
**Concept ID:** DYN-013-004

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `from . import module` or `from .. import module` | |
| JavaScript | `import from './module'` | |
| Ruby | `require_relative 'module'` | |
| PHP | Relative file paths in `require` | |

---

### DOMAIN: DYN-014 (Object Patterns)

#### Concept: define_class
**Intent:** Create class  
**Concept ID:** DYN-014-001

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `class Name:` | |
| JavaScript | `class Name {}` | |
| Ruby | `class Name ... end` | |
| PHP | `class Name {}` | |

---

#### Concept: instantiate
**Intent:** Create object instance  
**Concept ID:** DYN-014-002

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `instance = ClassName(args)` | |
| JavaScript | `instance = new ClassName(args)` | |
| Ruby | `instance = ClassName.new(args)` | |
| PHP | `$instance = new ClassName($args)` | |

---

#### Concept: define_method
**Intent:** Add method to class  
**Concept ID:** DYN-014-003

**Standard pattern across all 4 languages**

---

#### Concept: inheritance
**Intent:** Extend parent class  
**Concept ID:** DYN-014-004

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `class Child(Parent):` | |
| JavaScript | `class Child extends Parent` | |
| Ruby | `class Child < Parent` | |
| PHP | `class Child extends Parent` | |

---

#### Concept: super_call
**Intent:** Call parent method  
**Concept ID:** DYN-014-005

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `super().method()` | |
| JavaScript | `super.method()` | |
| Ruby | `super` or `super(args)` | |
| PHP | `parent::method()` | |

---

#### Concept: static_method
**Intent:** Define class method  
**Concept ID:** DYN-014-006

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `@staticmethod` or `@classmethod` | |
| JavaScript | `static method()` | |
| Ruby | `def self.method` | |
| PHP | `static function method()` | |

---

#### Concept: property
**Intent:** Define getter/setter  
**Concept ID:** DYN-014-007

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `@property` decorator | |
| JavaScript | `get name()` / `set name(value)` | |
| Ruby | `attr_accessor :name` | |
| PHP | `__get()` / `__set()` magic methods | |

---

#### Concept: instance_check
**Intent:** Check object type  
**Concept ID:** DYN-014-008

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `isinstance(obj, Class)` | |
| JavaScript | `obj instanceof Class` | |
| Ruby | `obj.is_a?(Class)` | |
| PHP | `$obj instanceof Class` | |

---

### DOMAIN: DYN-015 (DOM Manipulation - JavaScript Heavy)

#### Concept: select_element
**Intent:** Find DOM element  
**Concept ID:** DYN-015-001

| Language | Primary Use |
|----------|-------------|
| JavaScript | `document.querySelector(selector)` |
| Python | N/A (server-side) |
| Ruby | N/A (server-side) |
| PHP | N/A (server-side, or DOMDocument) |

---

#### Concept: select_elements
**Intent:** Find multiple DOM elements  
**Concept ID:** DYN-015-002

**Primary: JavaScript** `document.querySelectorAll(selector)`

---

#### Concept: create_element
**Intent:** Create new DOM element  
**Concept ID:** DYN-015-003

**Primary: JavaScript** `document.createElement(tag)`

---

#### Concept: append_child
**Intent:** Add element to parent  
**Concept ID:** DYN-015-004

**Primary: JavaScript** `parent.appendChild(child)`

---

#### Concept: set_attribute
**Intent:** Set element attribute  
**Concept ID:** DYN-015-005

**Primary: JavaScript** `element.setAttribute(name, value)`

---

#### Concept: add_event_listener
**Intent:** Attach event handler  
**Concept ID:** DYN-015-006

**Primary: JavaScript** `element.addEventListener(event, handler)`

---

### DOMAIN: DYN-016 (DateTime Operations)

#### Concept: current_timestamp
**Intent:** Get current time  
**Concept ID:** DYN-016-001

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `datetime.now()` or `time.time()` | |
| JavaScript | `new Date()` or `Date.now()` | |
| Ruby | `Time.now` | |
| PHP | `time()` or `new DateTime()` | |

---

#### Concept: parse_date
**Intent:** Parse date string  
**Concept ID:** DYN-016-002

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `datetime.strptime(string, format)` | |
| JavaScript | `new Date(string)` or `Date.parse(string)` | |
| Ruby | `DateTime.parse(string)` | |
| PHP | `strtotime($string)` or `DateTime::createFromFormat()` | |

---

#### Concept: format_date
**Intent:** Convert date to string  
**Concept ID:** DYN-016-003

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `dt.strftime(format)` | |
| JavaScript | `date.toISOString()` or custom formatting | |
| Ruby | `dt.strftime(format)` | |
| PHP | `date($format, $timestamp)` | |

---

#### Concept: date_arithmetic
**Intent:** Add/subtract time  
**Concept ID:** DYN-016-004

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `datetime + timedelta(days=1)` | |
| JavaScript | Manual millisecond arithmetic | |
| Ruby | `date + 1` (days) | |
| PHP | `date_add()` or `DateTime::modify()` | |

---

#### Concept: date_difference
**Intent:** Compare dates  
**Concept ID:** DYN-016-005

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `(dt2 - dt1).days` | |
| JavaScript | `(date2 - date1) / (1000 * 60 * 60 * 24)` | |
| Ruby | `(date2 - date1).to_i` | |
| PHP | `date_diff($dt1, $dt2)` | |

---

#### Concept: timezone_conversion
**Intent:** Convert between timezones  
**Concept ID:** DYN-016-006

**All languages have timezone libraries**

---

### DOMAIN: DYN-017 (Regex Patterns)

#### Concept: regex_match
**Intent:** Test pattern match  
**Concept ID:** DYN-017-001

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `re.match(pattern, string)` | |
| JavaScript | `pattern.test(string)` | |
| Ruby | `string =~ /pattern/` | |
| PHP | `preg_match($pattern, $string)` | |

---

#### Concept: regex_find
**Intent:** Extract matches  
**Concept ID:** DYN-017-002

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `re.findall(pattern, string)` | |
| JavaScript | `string.match(pattern)` | |
| Ruby | `string.scan(/pattern/)` | |
| PHP | `preg_match_all($pattern, $string, $matches)` | |

---

#### Concept: regex_replace
**Intent:** Replace pattern  
**Concept ID:** DYN-017-003

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `re.sub(pattern, replacement, string)` | |
| JavaScript | `string.replace(pattern, replacement)` | |
| Ruby | `string.gsub(/pattern/, replacement)` | |
| PHP | `preg_replace($pattern, $replacement, $string)` | |

---

#### Concept: regex_split
**Intent:** Split by pattern  
**Concept ID:** DYN-017-004

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `re.split(pattern, string)` | |
| JavaScript | `string.split(pattern)` | |
| Ruby | `string.split(/pattern/)` | |
| PHP | `preg_split($pattern, $string)` | |

---

### DOMAIN: DYN-018 (Environment Config)

#### Concept: get_env_var
**Intent:** Read environment variable  
**Concept ID:** DYN-018-001

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `os.environ['VAR']` or `os.getenv('VAR')` | |
| JavaScript | `process.env.VAR` | |
| Ruby | `ENV['VAR']` | |
| PHP | `$_ENV['VAR']` or `getenv('VAR')` | |

---

#### Concept: set_env_var
**Intent:** Set environment variable  
**Concept ID:** DYN-018-002

| Language | Syntax | Notes |
|----------|--------|-------|
| Python | `os.environ['VAR'] = 'value'` | |
| JavaScript | `process.env.VAR = 'value'` | |
| Ruby | `ENV['VAR'] = 'value'` | |
| PHP | `putenv('VAR=value')` | |

---

#### Concept: load_dotenv
**Intent:** Load .env file  
**Concept ID:** DYN-018-003

**All languages have dotenv libraries**

---

#### Concept: config_file
**Intent:** Load configuration  
**Concept ID:** DYN-018-004

**All languages have config file libraries (JSON, YAML, INI)**

---

## 4. POD A SUMMARY STATISTICS

**Total Concepts:** 106  
**Fully Mapped (all 4 languages):** 92 (87%)  
**Partially Mapped (2-3 languages):** 10 (9%)  
**Language-Specific (1 language):** 4 (4%)

**Most Common Concepts:**
1. List operations (12 concepts)
2. String manipulation (10 concepts)
3. Dictionary operations (8 concepts)
4. HTTP operations (8 concepts)
5. Object patterns (8 concepts)

**Language-Specific Strengths:**
- **JavaScript:** DOM manipulation, async/await (best support)
- **Python:** List comprehensions, data science libraries
- **Ruby:** Elegant syntax, blocks, metaprogramming
- **PHP:** Web-specific functions, superglobals

---

## 5. EXTRACTION GUIDELINES FOR POD A SPECIALISTS

### 5.1 For Python Specialist

**Focus on:**
- Pythonic idioms (comprehensions, generators, decorators)
- Standard library first (avoid external dependencies initially)
- Type hints for clarity (though dynamic at runtime)
- PEP standards compliance

**Avoid:**
- Overly clever one-liners that obscure intent
- Python 2 patterns
- Non-standard libraries unless necessary

---

### 5.2 For JavaScript Specialist

**Focus on:**
- Modern ES6+ syntax (arrow functions, destructuring, spread)
- Async/await over callbacks
- Promise patterns
- Both browser and Node.js contexts

**Avoid:**
- var declarations (use const/let)
- Callback hell
- Non-standard browser APIs

---

### 5.3 For Ruby Specialist

**Focus on:**
- Ruby idioms (blocks, symbols, metaprogramming)
- Enumerable methods
- Convention over configuration
- Rails patterns where applicable

**Avoid:**
- Perl-isms (unless idiomatic Ruby)
- Over-metaprogramming that obscures logic
- Ruby 1.9 patterns

---

### 5.4 For PHP Specialist

**Focus on:**
- Modern PHP 7.4+ / 8+ features
- Type declarations
- Composer ecosystem
- PSR standards

**Avoid:**
- PHP 5 patterns
- Global state ($_GET, $_POST without validation)
- Register globals mentality

---

## APPENDIX: CONCEPT CROSS-REFERENCE

**Most Universal Concepts (100% coverage across all 4 languages):**
- List filter, map, reduce, sort
- String concat, split, replace
- Dictionary get, set, delete
- Error try/catch
- Function definition and closures
- Control flow (if, while, for)

**Language Gaps:**
- **Async patterns:** PHP and Ruby have limited native support
- **DOM manipulation:** Only JavaScript (others server-side)
- **Type systems:** All dynamic, but varying degrees of optional typing

**Evolution Considerations:**
- JavaScript gaining more Python-like features (async/await, modules)
- PHP modernizing rapidly (type declarations, attributes)
- Ruby considering pattern matching and type annotations
- Python adding structural pattern matching

---

**Document End**
