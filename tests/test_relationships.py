
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from generation.chapter import ChapterGenerator

# Mock objects
class MockAI:
    def stream_chat(self, *args, **kwargs): yield ""

class MockStorage:
    def load_world_state(self, project):
        # Return a snippet of the actual JSON structure I just wrote
        return {
          "characters": [
            {
              "name": "沈焱笙",
              "role": "主角",
              "level": "怨灵",
              "relationships": [
                {"target": "沈嶂离", "relation_type": "仇敌/生父", "description": "杀母之仇"},
                {"target": "青云子", "relation_type": "盟友"}
              ]
            }
          ]
        }
    def list_chapters(self, project): return []
    def _get_project_dir(self, project): return "/tmp"
    @property
    def base_dir(self): return "/tmp"

def test_relationship_context():
    gen = ChapterGenerator("幽狱志", ai_client=MockAI(), storage=MockStorage())
    context = gen._build_context()
    print(context)
    
    if "关系: 仇敌/生父->沈嶂离(杀母之仇)" in context:
        print("\n✅ Verification SUCCESS: Relationship found in context.")
    else:
        print("\n❌ Verification FAILED: Relationship NOT found.")

if __name__ == "__main__":
    test_relationship_context()
