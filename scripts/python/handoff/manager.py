import os
import json
import subprocess
import datetime
import tempfile
from lib.store import Vibe3Store

class HandoffManager:
    def __init__(self, json_output=False, auto_confirm=False):
        self.store = Vibe3Store()
        self.json_output = json_output
        self.auto_confirm = auto_confirm

    def _get_current_branch(self):
        return subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode().strip()

    def _get_handoff_dir(self, branch):
        # branch-safe name (replace / with _)
        safe_name = branch.replace('/', '_')
        handoff_dir = os.path.join('.agent', 'handoff', safe_name)
        if not os.path.exists(handoff_dir):
            os.makedirs(handoff_dir, exist_ok=True)
        return handoff_dir

    def auth(self, role, agent, model):
        branch = self._get_current_branch()
        actor = f"{agent}/{model}" if agent and model else (agent or model or "unknown")
        
        updates = {}
        if role == 'plan':
            updates['planner_actor'] = actor
        elif role == 'report':
            updates['executor_actor'] = actor
        elif role == 'audit':
            updates['reviewer_actor'] = actor
            
        self.store.update_flow_state(branch, **updates)
        print(f"Registered {actor} as {role} for branch {branch}")

    def show(self, handoff_type=None):
        branch = self._get_current_branch()
        items = self.store.get_handoff_items(branch, handoff_type)
        
        if self.json_output:
            print(json.dumps(items, indent=2))
            return

        state = self.store.get_flow_state(branch)
        if not state:
            print(f"No flow record found for branch {branch}")
            return

        print(f"--- Handoff: {handoff_type or 'All'} for {branch} ---")
        if not items:
            print("No items recorded.")
        else:
            current_type = None
            for item in items:
                if item['type'] != current_type:
                    current_type = item['type']
                    print(f"\n[{current_type.upper()}]")
                print(f"#{item['item_number']} [{item['actor']}] ({item['updated_at']})")
                print(f"  {item['content']}")
        print("------------------------------------------")

    def edit(self, handoff_type):
        branch = self._get_current_branch()
        handoff_dir = self._get_handoff_dir(branch)
        filepath = os.path.join(handoff_dir, f"{handoff_type}.json")
        
        # 1. Load from DB to file if it doesn't exist or to ensure sync
        db_items = self.store.get_handoff_items(branch, handoff_type)
        
        data = {
            "branch": branch,
            "type": handoff_type,
            "items": []
        }
        
        for item in db_items:
            # JSON only keeps human-editable fields, omit timestamps
            data['items'].append({
                "item_number": item['item_number'],
                "actor": item['actor'],
                "content": item['content']
            })
            
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
            
        # 2. Open editor
        editor = os.environ.get('EDITOR', 'vi')
        subprocess.call([editor, filepath])
        
        # 3. Sync back to DB
        self._sync_file_to_db(filepath)

    def sync(self, handoff_type=None):
        branch = self._get_current_branch()
        handoff_dir = self._get_handoff_dir(branch)
        
        types = [handoff_type] if handoff_type else ['plan', 'report', 'audit']
        for t in types:
            filepath = os.path.join(handoff_dir, f"{t}.json")
            if os.path.exists(filepath):
                self._sync_file_to_db(filepath)
            else:
                if handoff_type:
                    print(f"No handoff file found for {t} at {filepath}")

    def _sync_file_to_db(self, filepath):
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        branch = data['branch']
        handoff_type = data['type']
        raw_items = data['items']
        
        # Get current state for authorship
        state = self.store.get_flow_state(branch)
        default_actor = "unknown"
        if handoff_type == 'plan':
            default_actor = state.get('planner_actor', 'unknown')
        elif handoff_type == 'report':
            default_actor = state.get('executor_actor', 'unknown')
        elif handoff_type == 'audit':
            default_actor = state.get('reviewer_actor', 'unknown')
            
        # Get existing items to keep track of max item_number
        existing_items = self.store.get_handoff_items(branch, handoff_type)
        max_num = max([i['item_number'] for i in existing_items]) if existing_items else 0
        
        processed_items = []
        now = datetime.datetime.now().isoformat()
        
        for i, item in enumerate(raw_items):
            content = item.get('content', '')
            if not content:
                continue
                
            item_num = item.get('item_number')
            actor = item.get('actor')
            created_at = item.get('created_at')
            updated_at = item.get('updated_at')
            
            if not item_num:
                # new item
                max_num += 1
                item_num = max_num
                actor = default_actor
                created_at = now
                updated_at = now
            else:
                # existing item, check if content changed
                # find in existing_items
                found = next((ei for ei in existing_items if ei['item_number'] == item_num), None)
                if found:
                    if found['content'] != content:
                        updated_at = now
                else:
                    # manually assigned number but not in DB? Treat as new but keep number
                    actor = actor or default_actor
                    created_at = created_at or now
                    updated_at = updated_at or now
            
            processed_items.append({
                "item_number": item_num,
                "actor": actor or default_actor,
                "content": content,
                "created_at": created_at or now,
                "updated_at": updated_at or now
            })
            
        self.store.sync_handoff_items(branch, handoff_type, processed_items)
        print(f"Synced {len(processed_items)} {handoff_type} items from JSON to SQLite.")
