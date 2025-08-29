# Complete htmx and hyperscript Documentation

## Table of Contents

1. [Introduction](#introduction)
2. [htmx Documentation](#htmx-documentation)
3. [hyperscript Documentation](#hyperscript-documentation)
4. [Integration and Best Practices](#integration-and-best-practices)
5. [Reference](#reference)

---

## Introduction

**htmx** and **hyperscript** are two complementary libraries that bring modern web development capabilities directly to HTML, emphasizing simplicity and locality of behavior over complex JavaScript frameworks.

### htmx
htmx gives you access to AJAX, CSS Transitions, WebSockets and Server Sent Events directly in HTML, using attributes, so you can build modern user interfaces with the simplicity and power of hypertext. htmx is small (~14k min.gz'd), dependency-free, extendable & has reduced code base sizes by 67% when compared with react.

### hyperscript
hyperscript is a scripting language for doing front end web development. It is designed to make it very easy to respond to events and do simple DOM manipulation in code that is directly embedded on elements on a web page.

Both libraries emphasize **Locality of Behavior** over **Separation of Concerns**, making code easier to understand and maintain.

---

# htmx Documentation

## Installation

htmx is a dependency-free, browser-oriented javascript library. Using it is as simple as adding a `<script>` tag to your document head.

### Via CDN

The fastest way to get going with htmx is to load it via a CDN:

```html
<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.6/dist/htmx.min.js" 
        integrity="sha384-Akqfrbj/HpNVo8k11SXBb6TlBWmXXlYQrCSqEWmyKJe+hDm3Z/B2WVG4smwBkRVm" 
        crossorigin="anonymous"></script>
```

Unminified version:
```html
<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.6/dist/htmx.js" 
        integrity="sha384-ksKjJrwjL5VxqAkAZAVOPXvMkwAykMaNYegdixAESVr+KqLkKE8XBDoZuwyWVUDv" 
        crossorigin="anonymous"></script>
```

### Download and Include

Download `htmx.min.js` from jsDelivr and include it:

```html
<script src="/path/to/htmx.min.js"></script>
```

### NPM Installation

```bash
npm install htmx.org@2.0.6
```

For webpack:
```javascript
import 'htmx.org';
window.htmx = require('htmx.org');
```

## Core Concepts

### Basic Example

```html
<button hx-post="/clicked" hx-swap="outerHTML">
  Click Me!
</button>
```

This tells htmx: "When a user clicks on this button, issue an HTTP POST request to '/clicked' and replace the entire button with the HTML response".

### Core Attributes

The core of htmx is a set of attributes that allow you to issue AJAX requests directly from HTML:

| Attribute | Description |
|-----------|-------------|
| `hx-get` | Issues a `GET` request to the given URL |
| `hx-post` | Issues a `POST` request to the given URL |
| `hx-put` | Issues a `PUT` request to the given URL |
| `hx-patch` | Issues a `PATCH` request to the given URL |
| `hx-delete` | Issues a `DELETE` request to the given URL |

### Triggering Requests

By default, AJAX requests are triggered by the "natural" event of an element:
- `input`, `textarea` & `select` are triggered on the `change` event
- `form` is triggered on the `submit` event
- Everything else is triggered on the `click` event

You can customize this with `hx-trigger`:

```html
<div hx-post="/mouse_entered" hx-trigger="mouseenter">
  [Here Mouse, Mouse!]
</div>
```

### Trigger Modifiers

- `once` - only issue a request once
- `changed` - only issue a request if the value has changed
- `delay:<time interval>` - wait before issuing the request
- `throttle:<time interval>` - throttle requests
- `from:<CSS Selector>` - listen for the event on a different element

Example:
```html
<input type="text" name="q"
       hx-get="/search" 
       hx-trigger="keyup changed delay:500ms"
       hx-target="#search-results">
```

### Multiple Triggers

```html
<div hx-get="/clicked" hx-trigger="click[ctrlKey]">
  Control Click Me
</div>
```

### Special Events

- `load` - fires once when the element is first loaded
- `revealed` - fires once when an element first scrolls into the viewport
- `intersect` - fires once when an element first intersects the viewport

### Polling

```html
<div hx-get="/news" hx-trigger="every 2s"></div>
```

### Request Indicators

Use the `htmx-indicator` class to show loading indicators:

```html
<button hx-get="/click">
  Click Me!
  <img class="htmx-indicator" src="/spinner.gif">
</button>
```

### Targets

By default, the response replaces the innerHTML of the element that made the request. Use `hx-target` to specify a different target:

```html
<input type="text" hx-get="/search" hx-target="#search-results">
<div id="search-results"></div>
```

#### Extended CSS Selectors

- `this` - the element itself
- `closest <CSS selector>` - finds the closest parent matching the selector
- `next <CSS selector>` - finds the next element matching the selector
- `previous <CSS selector>` - finds the previous element matching the selector
- `find <CSS selector>` - finds the first child descendant matching the selector

### Swapping

The `hx-swap` attribute controls how content is swapped:

| Value | Description |
|-------|-------------|
| `innerHTML` | Default, replaces the inner HTML |
| `outerHTML` | Replaces the entire target element |
| `afterbegin` | Prepends content before the first child |
| `beforebegin` | Prepends content before the target |
| `beforeend` | Appends content after the last child |
| `afterend` | Appends content after the target |
| `delete` | Deletes the target element |
| `none` | Does not append content |

#### Swap Modifiers

```html
<button hx-post="/like" hx-swap="outerHTML ignoreTitle:true">Like</button>
```

Available modifiers:
- `transition` - use View Transitions API
- `swap` - delay between content clear and insert
- `settle` - delay between insert and settle
- `ignoreTitle` - ignore title tags in response
- `scroll` - scroll target to top/bottom
- `show` - scroll target into view

### View Transitions

Enable smooth page transitions:

```html
<!-- Global -->
<script>htmx.config.globalViewTransitions = true</script>

<!-- Per element -->
<button hx-get="/page" hx-swap="innerHTML transition:true">Navigate</button>
```

### Synchronization

Use `hx-sync` to coordinate requests between elements:

```html
<form hx-post="/store">
  <input id="title" name="title" type="text"
         hx-post="/validate"
         hx-trigger="change"
         hx-sync="closest form:abort">
  <button type="submit">Submit</button>
</form>
```

### CSS Transitions

Keep element IDs stable across requests to enable smooth CSS transitions:

```css
.red {
  color: red;
  transition: all ease-in 1s;
}
```

```html
<div id="div1">Original Content</div>
<!-- Server responds with: -->
<div id="div1" class="red">New Content</div>
```

### Out of Band Swaps

Update multiple parts of the page with a single request:

```html
<!-- Response HTML -->
<div id="message" hx-swap-oob="true">Swap me directly!</div>
Additional Content
```

### Parameters

Include form values and additional parameters:

```html
<!-- Include other elements -->
<button hx-post="/submit" hx-include="#extra-input">Submit</button>

<!-- Add extra values -->
<button hx-post="/submit" hx-vals='{"key": "value"}'>Submit</button>

<!-- Dynamic values -->
<button hx-post="/submit" hx-vars="key:computeValue()">Submit</button>
```

### File Uploads

```html
<form hx-post="/upload" hx-encoding="multipart/form-data">
  <input type="file" name="file">
  <button type="submit">Upload</button>
</form>
```

### Confirmation

```html
<button hx-delete="/account" 
        hx-confirm="Are you sure you wish to delete your account?">
  Delete My Account
</button>
```

### Validation

htmx integrates with HTML5 validation:

```html
<form hx-post="/submit">
  <input name="email" type="email" required>
  <button type="submit">Submit</button>
</form>
```

### Boosting

Progressive enhancement for regular links and forms:

```html
<div hx-boost="true">
  <a href="/blog">Blog</a>
</div>
```

### History Management

```html
<a hx-get="/blog" hx-push-url="true">Blog</a>
```

Configuration:
- `hx-history-elt` - specify element for snapshots
- `hx-history="false"` - disable history for sensitive data

### Response Handling

Default response handling:
- 2xx/3xx responses are swapped
- 4xx/5xx responses trigger error events
- 204 No Content does nothing

Custom response handling:
```html
<meta name="htmx-config" content='{
  "responseHandling": [
    {"code":"422", "swap": true},
    {"code":"[45]..", "swap": false, "error":true}
  ]
}'>
```

### Request Headers

htmx includes these headers in requests:

| Header | Description |
|--------|-------------|
| `HX-Request` | Always `true` |
| `HX-Trigger` | ID of triggered element |
| `HX-Trigger-Name` | Name of triggered element |
| `HX-Target` | ID of target element |
| `HX-Current-URL` | Current page URL |
| `HX-Boosted` | `true` if request is via hx-boost |

### Response Headers

Server can include these headers:

| Header | Description |
|--------|-------------|
| `HX-Location` | Client-side redirect |
| `HX-Push-Url` | Push URL to browser history |
| `HX-Redirect` | Client-side redirect |
| `HX-Refresh` | Refresh the page |
| `HX-Replace-Url` | Replace current URL |
| `HX-Reswap` | Override swap method |
| `HX-Retarget` | Override target selector |
| `HX-Trigger` | Trigger client-side events |

### Events

htmx fires many events during the request lifecycle:

| Event | Description |
|-------|-------------|
| `htmx:beforeRequest` | Before request is made |
| `htmx:beforeSwap` | Before content is swapped |
| `htmx:afterSwap` | After content is swapped |
| `htmx:afterSettle` | After new content is settled |
| `htmx:load` | When any new content is loaded |
| `htmx:configRequest` | Configure request parameters |

Example event handling:
```javascript
document.body.addEventListener('htmx:configRequest', function(evt) {
  evt.detail.headers['Auth-Token'] = getAuthToken();
});
```

### Extensions

htmx supports extensions for additional functionality:

```html
<script src="https://unpkg.com/htmx.org@2.0.6/dist/htmx.min.js"></script>
<script src="https://unpkg.com/htmx.org@2.0.6/dist/ext/response-targets.js"></script>

<body hx-ext="response-targets">
  <button hx-post="/register" 
          hx-target="#response-div" 
          hx-target-404="#not-found">
    Register!
  </button>
</body>
```

### JavaScript API

```javascript
// Make AJAX request
htmx.ajax('GET', '/api/data', '#results');

// Process new content
htmx.process(document.getElementById('new-content'));

// Trigger events
htmx.trigger('#myDiv', 'myEvent', {detail: 'data'});

// Find elements
htmx.find('#myDiv');
htmx.findAll('.myClass');

// Add/remove classes
htmx.addClass(element, 'myClass');
htmx.removeClass(element, 'myClass');
```

### Configuration

```javascript
htmx.config.defaultSwapStyle = 'outerHTML';
htmx.config.defaultSwapDelay = 100;
htmx.config.timeout = 30000;
htmx.config.selfRequestsOnly = true;
```

Or via meta tag:
```html
<meta name="htmx-config" content='{"defaultSwapStyle":"outerHTML"}'>
```

### Security

- Always escape user content
- Use `hx-disable` to prevent htmx processing in untrusted areas
- Configure `selfRequestsOnly` for additional security
- Use CSP headers
- Validate requests server-side

### Debugging

```javascript
// Log all events
htmx.logAll();

// Custom logger
htmx.logger = function(elt, event, data) {
  console.log(event, elt, data);
};
```

Browser console:
```javascript
// Monitor DOM events
monitorEvents(htmx.find("#theElement"));
```

---

# hyperscript Documentation

## Installation

hyperscript is a dependency-free JavaScript library:

```html
<script src="https://unpkg.com/hyperscript.org@0.9.14"></script>
```

With build step:
```javascript
import _hyperscript from 'hyperscript.org';
_hyperscript.browserInit();
```

## Basic Syntax

hyperscript is written directly in HTML using the `_` attribute:

```html
<button _="on click toggle .red on me">
  Click Me
</button>
```

Alternative attribute names:
- `script`
- `data-script`

## Comments

```hyperscript
-- Single line comment
/* Multi-line comment */
// JavaScript style comment
```

## Script Structure

A hyperscript consists of **features** (like event handlers), which contain **commands** (statements), which use **expressions**.

```hyperscript
on click          -- feature
  toggle .red     -- command
  on me           -- expression
```

## Variables and Scopes

### Creating Variables

```hyperscript
set x to 10
put "hello" into y
```

### Variable Scopes

- **Local** (default): `set x to 10`
- **Element**: `set :x to 10` or `set element x to 10`
- **Global**: `set $x to 10` or `set global x to 10`

```hyperscript
set x to 10        -- local
set :count to 0    -- element scoped
set $config to {}  -- global
```

### Attributes as Storage

```hyperscript
set @my-attr to 10     -- stores "10" in my-attr attribute
get @my-attr           -- gets the attribute value
```

## Special Symbols

| Symbol | Alias | Description |
|--------|-------|-------------|
| `result` | `it`, `its` | Result of last command |
| `me` | `my`, `I` | Current element |
| `event` | | Current event |
| `target` | | Event target |
| `body` | | Document body |
| `detail` | | Event detail |

## Basic Commands

### Logging

```hyperscript
log "Hello Console!"
log x, y, z
```

### Conditionals

```hyperscript
if x > 10
  log "Greater than 10"
else
  log "Less than or equal to 10"
end
```

Alternative syntax:
```hyperscript
log "Big number!" unless x <= 10
```

### Loops

```hyperscript
-- Basic for loop
for x in [1, 2, 3]
  log x
end

-- Repeat with conditions
repeat while x < 10
  increment x
end

repeat until x is 10
  increment x
end

-- Repeat with times
repeat 5 times
  log "Hello"
end

-- With index
for item in items index i
  log i, item
end
```

### Math Operations

```hyperscript
set x to 10
set y to 20
set sum to x + y
set diff to x - y
set product to x * y
set remainder to x mod 3

-- Must parenthesize complex expressions
set result to (x * x) + (y * y)

-- Increment/decrement
increment x
decrement y
```

### String Operations

```hyperscript
set hello to 'hello'
set world to "world"
set combined to hello + " " + world
set template to `${hello} ${world}`

-- Append to strings
get "hello"
append " world"
log it  -- "hello world"
```

## DOM Manipulation

### DOM Literals

```hyperscript
.className      -- elements with class
#elementId      -- element with ID
<css selector/> -- query selector
@attributeName  -- attribute value
*styleProperty  -- style property value
10px           -- measurement literal
```

### Finding Elements

```hyperscript
-- Class and ID literals
add .highlight to .tabs
remove @disabled from #submit-btn

-- Query literals
hide <div.modal/>
show <input[type="text"]/>

-- Relative selectors
get the closest <form/>
get the next <div/>
get the first <p/> in me
```

### Content Manipulation

```hyperscript
-- Set content
put "Hello" into #myDiv
set my innerHTML to "New content"

-- Position-based insertion
put "Before" before me
put "After" after me
put "At start" at the start of me
put "At end" at the end of me
```

### Class and Attribute Management

```hyperscript
-- Classes
add .active to me
remove .hidden from .dialog
toggle .selected on #item

-- Attributes  
add @disabled to #button
remove @required from input
toggle @checked on #checkbox

-- Styles
set my *color to 'red'
set my *width to 100px
toggle the *display of #panel
```

### Show/Hide

```hyperscript
show me
hide me
show me with *opacity    -- use opacity instead of display
hide me with *visibility -- use visibility

-- Conditional show
show <li/> in #list when its innerHTML contains my value
```

### Transitions and Animation

```hyperscript
-- CSS transitions
transition my *opacity to 0 over 300ms
transition my *transform to 'scale(1.5)' over 500ms then
transition my *transform to 'scale(1)' over 200ms

-- Wait for transitions
add .fade-out then settle then remove me
```

### Measurements

```hyperscript
measure my top, left, width, height
log `Element is ${width}px wide`

-- Computed styles
get my *computed-width
put it into #width-display
```

## Event Handling

### Basic Event Handlers

```hyperscript
on click
  toggle .active on me
end

on mouseenter
  add .hover to me
end

on submit
  prevent the default
  -- handle form submission
end
```

### Event Modifiers

```hyperscript
-- Event filters
on keyup[key=='Enter']
  log "Enter pressed"
end

on click[ctrlKey]
  log "Control+click"
end

-- Destructuring
on mousedown(button, clientX, clientY)
  log `Button ${button} at ${clientX}, ${clientY}`
end
```

### Event Timing and Queuing

```hyperscript
-- Execute every event (no queuing)
on every click
  add .clicked
end

-- Queue strategies
on click queue all    -- queue all events
on click queue first  -- queue first, drop rest
on click queue last   -- queue last, drop rest
on click queue none   -- drop events while busy
```

### Synthetic Events

```hyperscript
-- Mutation observer
on mutation of @data-count
  log "Count attribute changed"
end

-- Intersection observer
on intersection(intersecting) having threshold 0.5
  if intersecting
    transition opacity to 1
  else  
    transition opacity to 0
  end
end
```

## Sending Events

```hyperscript
-- Send custom events
send myEvent to #target
send dataReady(data: {x: 1, y: 2}) to .listeners
trigger customEvent on me

-- Send to multiple targets
send update to .dashboard, #sidebar
```

## Functions

### Defining Functions

```hyperscript
def greet(name)
  return `Hello, ${name}!`
end

def waitAndReturn()
  wait 2s
  return "I waited..."
end

-- Namespaced functions
def utils.formatDate(date)
  return date.toLocaleDateString()
end
```

### Calling Functions

```hyperscript
-- Direct calls
call greet('World')
log it

-- Get command (same as call)
get greet('Alice')
put it into #greeting

-- As standalone command
greet('Bob')
log result

-- Pseudo-command syntax
greet('Charlie') into #output
formatDate(new Date()) into #date-display
```

### Function Features

```hyperscript
def riskyFunction()
  call mightThrow()
  return "Success"
catch error
  log `Error: ${error}`
  return "Failed"
finally
  log "Cleanup"
end
```

## Async and Timing

### Waiting

```hyperscript
-- Wait for time
wait 2s
wait 500ms

-- Wait for events
wait for click
wait for myCustomEvent

-- Wait with timeout
wait for continue or 5s
if result's type is 'continue'
  log "Got continue event"
else
  log "Timed out"
end
```

### Async Transparency

Most operations are automatically async-transparent:

```hyperscript
-- Fetch appears synchronous but is async
fetch '/api/data'
put result into #display

-- Multiple async operations in sequence
fetch '/api/user'
set user to result
fetch `/api/posts/${user.id}`
put result into #posts
```

### Explicit Async

```hyperscript
-- Don't wait for completion
async call longRunningTask()
put "Started task..." into #status
```

## Object Manipulation

### Property Access

```hyperscript
set user to {name: "Alice", age: 30}

-- Different ways to access properties
log user.name           -- dot notation
log user['name']        -- bracket notation  
log user's name         -- possessive
log the name of user    -- of expression

-- Special possessives
log my innerHTML        -- same as me.innerHTML
log its value          -- same as it.value
```

### Array Operations

```hyperscript
set arr to [1, 2, 3]
log arr[0]              -- first element
log the first of arr    -- also first element  
log the last of arr     -- last element
log random in arr       -- random element

-- Flat mapping (like jQuery)
set divs to <div/>
set parents to the parent of divs  -- array of all parent elements
```

### Creating Objects

```hyperscript
-- Make command for constructors
make a URL from "/path", "https://example.com"
make a <button.primary/> called newBtn

-- Object literals
set config to {
  theme: 'dark',
  timeout: 5000
}
```

## Advanced Features

### Behaviors

Reusable code bundles:

```hyperscript
behavior Removable(removeButton)
  on click from removeButton
    remove me
  end
end
```

Install behaviors:
```html
<div class="banner" _="install Removable(removeButton: #close)">
  Content here
  <button id="close">×</button>
</div>
```

### Workers

Define web workers inline:

```hyperscript
worker Calculator
  def fibonacci(n)
    if n <= 1 then return n
    return fibonacci(n-1) + fibonacci(n-2)
  end
end
```

Use the worker:
```hyperscript
call Calculator.fibonacci(35)
put `Result: ${it}` into #result
```

### Sockets

WebSocket connections:

```hyperscript
socket ChatSocket ws://localhost:8080/chat
  on open
    log "Connected to chat"
  end
  
  on message as json
    put message.text into #chat
  end
end

-- Send messages
send chatMessage(text: "Hello!") to ChatSocket
```

### Server-Sent Events

```hyperscript
eventsource Updates from http://api.example.com/updates
  on message as string
    put it into #updates
  end
  
  on error
    log "Connection error"
  end
end
```

### Inline JavaScript

```hyperscript
-- Inline JS expressions
js return new Date().toISOString() end

-- JS with parameters
set name to "Alice"
js(name) return `Hello, ${name}!` end

-- Top-level JS functions
js
  function complexCalculation(x, y) {
    return Math.sqrt(x * x + y * y);
  }
end
```

## Type Conversions

```hyperscript
get "123" as Int        -- convert to integer
get "3.14" as Float     -- convert to float
get user as JSON        -- convert to JSON string
get jsonStr as Object   -- parse JSON
get elements as HTML    -- convert to HTML string
get form as Values      -- extract form values
get (123.456) as Fixed<2>  -- "123.46"
```

## Comparisons and Logic

### Natural Language Comparisons

```hyperscript
if x is 5                    -- same as x == 5
if x is not 5               -- same as x != 5
if no x                     -- x is null/undefined/empty
if x exists                 -- not (no x)
if I match .selected        -- CSS selector test
if x is greater than y      -- same as x > y
if list is empty           -- length is 0
if I am the result         -- identity comparison
```

### Combining Conditions

```hyperscript
if x > 5 and y < 10
  log "Both conditions true"
end

if user exists and user.active
  log "Active user"  
end
```

## Error Handling

### Try/Catch

```hyperscript
def safeDivide(a, b)
  if b is 0 then throw "Division by zero"
  return a / b
catch error
  log `Error: ${error}`
  return null
end
```

### Exception Events

```hyperscript
on exception(error)
  log `An error occurred: ${error}`
  -- handle gracefully
end
```

## Debugging

### Logging and Beep

```hyperscript
-- Simple logging
log "Debug point reached"
log myVariable, "has value:", myVariable

-- Beep operator for inline debugging
add .highlight to beep! <div.target/>
-- Logs: "The expression (<div.target/>) evaluates to: [div.target]"
```

### Breakpoints

```hyperscript
-- Using hyperscript debugger (hdb.js)
on click
  set x to 10
  breakpoint  -- pause execution here
  log x
end
```

## Integration with JavaScript

### Calling JS Functions

```hyperscript
-- Any global JS function can be called
call alert('Hello!')
call console.log('Debug info')

-- Method chaining
call document.querySelector('#myDiv').focus()
```

### htmx Integration

hyperscript works seamlessly with htmx:

```html
<button hx-post="/api/save" 
        _="on htmx:afterRequest 
           if event.detail.successful 
             add .saved to me 
             wait 2s 
             remove .saved from me">
  Save
</button>
```

### Processing New Content

```hyperscript
-- When adding content dynamically
put '<div _="on click log \'clicked\'">New</div>' into #container
call _hyperscript.processNode(#container)
```

---

# Integration and Best Practices

## Using htmx and hyperscript Together

htmx and hyperscript complement each other perfectly:

- **htmx**: Server communication, page updates, navigation
- **hyperscript**: Client-side interactivity, animations, local state

```html
<form hx-post="/submit" 
      _="on htmx:afterRequest 
         if event.detail.successful 
           add .success to me 
           wait 3s 
           remove .success from me">
  
  <input name="email" type="email" required
         _="on blur validate me">
  
  <button type="submit"
          _="on click add @disabled to me">
    Submit
  </button>
</form>
```

## Common Patterns

### Form Enhancement

```html
<form hx-post="/contact" hx-target="#result"
      _="on htmx:beforeRequest add .loading to me
         on htmx:afterRequest remove .loading from me">
  
  <input name="email" type="email"
         _="on input 
            if my value contains '@' 
              remove .error from me 
            else 
              add .error to me">
  
  <div id="result"></div>
</form>
```

### Dynamic Lists

```html
<ul id="todo-list">
  <li _="on click toggle .completed on me">
    <span>Task 1</span>
    <button _="on click remove closest <li/>">Delete</button>
  </li>
</ul>

<button hx-post="/todos" hx-target="#todo-list" hx-swap="beforeend"
        _="on click 
           set input to #new-todo 
           if input.value.length > 0 
             send submit">
  Add Todo
</button>
```

### Modal Dialogs

```html
<div id="modal" class="modal" 
     _="on show add .open to me 
        on hide remove .open from me
        on click from .modal-backdrop hide me">
  
  <div class="modal-content" _="on click halt the event">
    <button class="close" _="on click hide #modal">×</button>
    <div class="modal-body"></div>
  </div>
</div>

<button hx-get="/user-form" hx-target="#modal .modal-body"
        _="on htmx:afterSwap show #modal">
  Edit User
</button>
```

### Real-time Updates

```html
<div hx-sse="connect:/updates">
  <div hx-sse="swap:message"
       _="on htmx:sseMessage 
          add .flash to me 
          settle 
          remove .flash from me">
    Status: Connected
  </div>
</div>
```

## Performance Tips

### htmx Performance
- Use `hx-select` to return only needed content
- Implement proper caching headers
- Use `hx-sync` to avoid race conditions
- Consider `hx-boost` for progressive enhancement

### hyperscript Performance
- Use inline JavaScript for heavy computations
- Leverage web workers for complex operations  
- Minimize DOM queries with local variables
- Use event delegation for repeated elements

## Security Considerations

### Content Security Policy

Both libraries work with strict CSP:

```html
<meta http-equiv="Content-Security-Policy" 
      content="default-src 'self'; script-src 'self' 'unsafe-inline'">
```

### Input Sanitization

Always sanitize server responses:

```javascript
// Server-side (example with Express)
app.post('/submit', (req, res) => {
  const sanitizedInput = escapeHtml(req.body.content);
  res.send(`<div>${sanitizedInput}</div>`);
});
```

### Disable in Untrusted Areas

```html
<!-- htmx -->
<div hx-disable>
  <%= raw(user_content) %>
</div>

<!-- hyperscript -->
<div data-disable-scripting>
  <%= raw(user_content) %>
</div>
```

---

# Reference

## htmx Quick Reference

### Core Attributes

| Attribute | Description |
|-----------|-------------|
| `hx-get`, `hx-post`, `hx-put`, `hx-patch`, `hx-delete` | HTTP requests |
| `hx-trigger` | Event that triggers request |
| `hx-target` | Element to update |
| `hx-swap` | How to swap content |
| `hx-select` | Select part of response |
| `hx-include` | Include other form values |
| `hx-params` | Filter parameters |
| `hx-headers` | Additional headers |
| `hx-vals` | Extra values (JSON) |
| `hx-confirm` | Confirmation dialog |
| `hx-boost` | Progressive enhancement |
| `hx-push-url` | Update browser URL |
| `hx-ext` | Enable extensions |

### CSS Classes

| Class | Description |
|-------|-------------|
| `htmx-request` | Added during requests |
| `htmx-indicator` | Loading indicator |
| `htmx-swapping` | During content swap |
| `htmx-settling` | During settle phase |

### Configuration Options

```javascript
htmx.config = {
  // Core settings
  defaultSwapStyle: 'innerHTML',
  defaultSwapDelay: 0,
  defaultSettleDelay: 20,
  
  // Security
  selfRequestsOnly: true,
  allowEval: true,
  allowScriptTags: true,
  
  // History
  historyEnabled: true,
  historyCacheSize: 10,
  refreshOnHistoryMiss: false,
  
  // View Transitions
  globalViewTransitions: false,
  
  // Other
  timeout: 0,
  withCredentials: false,
  scrollBehavior: 'instant'
};
```

## hyperscript Quick Reference

### Basic Syntax

```hyperscript
-- Variables
set x to 10
set :elementVar to 20
set $globalVar to 30
set @my-attr to "value"

-- Conditionals  
if x > 5 then log x end
log x unless x <= 5

-- Loops
for item in items
  log item
end

repeat while x < 10
  increment x
end

-- Functions
def greet(name)
  return `Hello ${name}!`
end
```

### DOM Literals

```hyperscript
.className          -- class selector
#elementId          -- ID selector  
<css selector/>     -- query selector
@attributeName      -- attribute value
*styleProperty      -- style property
10px               -- measurement literal
```

### Event Handling

```hyperscript
on click               -- basic event
on click[ctrlKey]      -- filtered event
on click(clientX)      -- destructured event
on every click         -- no queuing
on click queue all     -- queue all events
```

### Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `set`/`put` | Assign values | `set x to 10` |
| `add`/`remove`/`toggle` | Modify classes/attributes | `toggle .active` |
| `show`/`hide` | Visibility | `hide me with *opacity` |
| `transition` | CSS transitions | `transition opacity to 0` |
| `wait` | Pause execution | `wait 2s` |
| `send`/`trigger` | Fire events | `send myEvent to #target` |
| `fetch` | HTTP requests | `fetch /api/data` |
| `call`/`get` | Function calls | `call myFunction()` |
| `log` | Console output | `log "debug info"` |
| `if`/`unless` | Conditionals | `if x > 5 then ... end` |
| `repeat`/`for` | Loops | `for item in list ... end` |
| `halt` | Stop event/exit | `halt the event` |
| `throw` | Throw exception | `throw "error message"` |

### Expressions Reference

| Type | Syntax | Example |
|------|--------|---------|
| Comparison | `is`, `is not`, `>`, `<`, etc. | `x is 5`, `x > y` |
| Logical | `and`, `or`, `not` | `x > 0 and y < 10` |
| Existence | `no`, `exists` | `no x`, `user exists` |
| CSS Match | `matches` | `I match .selected` |
| Positional | `first`, `last`, `random` | `first <div/>` |
| Relative | `next`, `previous`, `closest` | `next <p/>` |
| Measurement | `px`, `em`, `%`, etc. | `10px`, `50%` |

This comprehensive documentation covers both htmx and hyperscript, providing everything needed to build modern web applications with these powerful, simple tools. Both libraries emphasize locality of behavior and simplicity, making them excellent choices for developers who want to enhance HTML without the complexity of large JavaScript frameworks.