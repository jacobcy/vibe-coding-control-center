I will modify the configuration and installation logic to strictly follow the "no auto-creation" policy and ensure the correct flow of keys from the project to the user's home directory.

1.  **Modify `bin/vibe-config`**:
    *   **Audit & Fix**: Remove the logic in `init_config_home` that automatically copies `keys.template.env` to `~/.vibe/keys.env` if the file is missing.
    *   **Improve Feedback**: Update `show_config` and `init_config` to display a clear warning/instruction if `keys.env` is missing, telling the user to create it manually or run the installation script, instead of saying it was created from a template.

2.  **Modify `scripts/install.sh`**:
    *   **Update Logic**: Change the installation step to look for `config/keys.env` (the configured keys file) instead of `config/keys.template.env`.
    *   **Action**: If `config/keys.env` exists, copy it to `~/.vibe/keys.env`.
    *   **Fallback**: If `config/keys.env` is missing, log a warning informing the user that no configuration was found and they should configure `~/.vibe/keys.env` manually (preserving the existing behavior of not overwriting if it already exists).

This ensures that `keys.env` is only created when explicitly intended (either by the user manually, or by the install script if the user prepared the source file), and avoids silent/implicit creation of default templates.
