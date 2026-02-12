import { useState, useMemo } from 'react';
import { Command } from 'cmdk';
import { useHotkeys } from 'react-hotkeys-hook';
import { useCommandRegistryStore, CommandItem } from '../store/shortcutsRegistry';
import styles from './CommandPalette.module.css';

export const CommandPalette: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  
  const commands = useCommandRegistryStore((state) => state.commands);
  const recentIds = useCommandRegistryStore((state) => state.recentIds);
  const trackExecution = useCommandRegistryStore((state) => state.trackExecution);

  // Bind keyboard shortcuts to toggle command palette
  useHotkeys('mod+k', (e) => {
    e.preventDefault();
    setOpen((prev) => !prev);
  }, { enableOnFormTags: true });

  // Filter and prioritize commands based on query and recency
  const filteredCommands = useMemo(() => {
    if (!search.trim()) {
      // Prioritize recently executed commands
      const recent = commands.filter((cmd) => recentIds.includes(cmd.id));
      const remaining = commands.filter((cmd) => !recentIds.includes(cmd.id));
      return { recent, remaining };
    }

    const query = search.toLowerCase();
    const matches = commands.filter((cmd) => {
      return (
        cmd.label.toLowerCase().includes(query) ||
        (cmd.hint && cmd.hint.toLowerCase().includes(query)) ||
        (cmd.keywords && cmd.keywords.some((kw) => kw.toLowerCase().includes(query)))
      );
    });

    return { recent: [], remaining: matches };
  }, [search, commands, recentIds]);

  const handleSelect = (cmd: CommandItem) => {
    trackExecution(cmd.id);
    cmd.execute();
    setOpen(false);
    setSearch('');
  };

  // Group remaining commands by category
  const groupedRemaining = useMemo(() => {
    const groups: { [key: string]: CommandItem[] } = {};
    filteredCommands.remaining.forEach((cmd) => {
      const category = cmd.category;
      if (!groups[category]) {
        groups[category] = [];
      }
      groups[category].push(cmd);
    });
    return groups;
  }, [filteredCommands.remaining]);

  if (!open) return null;

  return (
    <div className={styles.dialogOverlay} onClick={() => setOpen(false)}>
      <div className={styles.paletteContainer} onClick={(e) => e.stopPropagation()}>
        <Command label="Command Palette">
          <Command.Input
            placeholder="Type a command or search..."
            value={search}
            onValueChange={setSearch}
            className={styles.input}
            autoFocus
          />
          <Command.List className={styles.list}>
            <Command.Empty className={styles.empty}>No results found.</Command.Empty>

            {/* Recent Group */}
            {filteredCommands.recent.length > 0 && (
              <Command.Group heading={<span className={styles.groupHeading}>Recent Commands</span>}>
                {filteredCommands.recent.map((cmd) => (
                  <Command.Item
                    key={`recent-${cmd.id}`}
                    value={cmd.label}
                    onSelect={() => handleSelect(cmd)}
                    className={styles.item}
                  >
                    <span>{cmd.label}</span>
                    {cmd.shortcut && <span className={styles.shortcut}>{cmd.shortcut}</span>}
                  </Command.Item>
                ))}
              </Command.Group>
            )}

            {/* Categorized Groups */}
            {Object.entries(groupedRemaining).map(([category, items]) => (
              <Command.Group
                key={category}
                heading={<span className={styles.groupHeading}>{category.toUpperCase()}</span>}
              >
                {items.map((cmd) => (
                  <Command.Item
                    key={cmd.id}
                    value={cmd.label}
                    onSelect={() => handleSelect(cmd)}
                    className={styles.item}
                  >
                    <span>{cmd.label}</span>
                    {cmd.shortcut && <span className={styles.shortcut}>{cmd.shortcut}</span>}
                  </Command.Item>
                ))}
              </Command.Group>
            ))}
          </Command.List>
        </Command>
      </div>
    </div>
  );
};
