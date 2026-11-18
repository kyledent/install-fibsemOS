# Reaching the microscope PC's share

`--from-mpc` reads the AutoScript wheels straight from the microscope PC (MPC)
over the network, using this path:

```
\\<mpc-host>\C$\Program Files\Thermo Scientific AutoScript\PythonPackages
```

`C$` is Windows' hidden administrative share. Reading it needs:

- the MPC switched on and reachable from the support PC;
- an account with **administrator rights on the MPC**;
- those credentials available to the support PC's Windows session.

The support PC and the MPC are usually in different accounts or domains, so
the third point rarely holds on its own. `cmdkey` fixes it once.

## Cache the credentials with `cmdkey`

In any Windows prompt on the support PC (PowerShell or cmd):

```cmd
cmdkey /add:192.168.0.1 /user:MPC-ADMIN-USER
```

Use your MPC's address and an admin account on it: a local account
(`Administrator`) or `DOMAIN\user`. Leave out `/pass:` and Windows prompts for
the password, so it never appears in your shell history.

Check that it was stored:

```cmd
cmdkey /list:192.168.0.1
```

Test it. This should list the wheels without asking for a password:

```cmd
dir "\\192.168.0.1\C$\Program Files\Thermo Scientific AutoScript\PythonPackages"
```

Or use the repo's own check:

```cmd
python install_autoscript_wheels.py --from-mpc --list
```

Remove the credential when the support PC is retired or the password changes:

```cmd
cmdkey /delete:192.168.0.1
```

Windows Credential Manager encrypts what `cmdkey` stores (DPAPI) under your
Windows user, so other users of the PC cannot read it. It persists across
reboots.

## No admin account on the MPC?

Ask whoever manages the MPC for one of these:

1. **A read-only share of just the wheel folder**, e.g. `\\<mpc-host>\AutoScriptWheels`.
   Then point the template at it in `config.json`:
   ```json
   { "mpc": { "wheel_share_template": "\\\\{host}\\AutoScriptWheels" } }
   ```
2. **A copy of the folder** on a USB stick or network drive, and install with:
   ```
   python install.py --wheels E:\PythonPackages
   ```

Option 2 also works when the MPC is off. Copy the folder again after every
AutoScript upgrade.

## Firewall and routing

The share uses SMB (TCP 445). fibsemOS itself only needs the AutoScript port
(TCP 7520 by default). If `--from-mpc` fails but this succeeds:

```
python verify.py --check-network
```

then SMB is blocked between the two PCs, not AutoScript. Use the `--wheels`
route instead.
