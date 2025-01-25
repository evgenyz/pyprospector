Setup
---

`pip install -r requirements.txt`

**Note**
Or use any other mechanism to install dependencies.

Content
---

Content *plans* are defined in `content/profiles/*.yaml` (*e8.yaml* is currently the only plan defined). They refer to tests from `content/tests`.

Build the content:

```shell
cd content
./build
cd ..
```

The resulting *plan*, consumable by `pyprospector`, resides in the `artifacts` directory (since we have only one profile E8, it would be `e8.json`).

There is also a set of all the *tests* in JSON format.

Prospector
---

Execute a *plan*:

```shell
./prospector content/artifacts/e8.json
```

Execute an individual *test*:

```shell
./prospector content/artifacts/no_empty_passwords.json
```

**Note**
Prospector will automatically wrap the test (or multiple tests) into an artificial plan and execute it.

Execute an individual *test* with JSON output only:

```shell
./prospector content/artifacts/no_empty_passwords.json -j
```

Execute an individual *test* and generate [Markdeep](https://casual-effects.com/markdeep/) *report* (which would self-render as HTML by your browser):

```shell
./prospector content/artifacts/sudo_remove_nopasswd.json -r report.md.html 
```

Execute an individual *test* in a running container:

```shell
./prospector content/artifacts/no_empty_passwords.json -T container://container_name
```

Execute an individual *test* on a different host:

```shell
./prospector content/artifacts/no_empty_passwords.json -T ssh://hostname
```
**Note** 
Very limited and experimental: interactive auth is not supported at this moment, and the same goes for sudo (for it to work you must allow the user to run sudo without password).