#!/usr/bin/env python3
"""
Liao Knowledge Base Demo

This script demonstrates how to use Liao's knowledge base integration
with GangDan-compatible ChromaDB format.

Requirements:
    pip install chromadb requests
    
Usage:
    python examples/kb_demo.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from liao.knowledge import KBConfig, KBManager


def demo_basic_usage():
   """Demonstrate basic KB usage."""
  print("=" * 60)
  print("Liao Knowledge Base Demo")
  print("=" * 60)
    
   # Configure KB - can point to GangDan's ChromaDB
  config = KBConfig(
       chroma_dir=str(Path.home() / "GangDan" / "data" / "chroma"),
     embedding_model="nomic-embed-text",
      ollama_url="http://localhost:11434",
      strict_kb_mode=False,
   )
    
   # Create manager
  manager = KBManager(config)
    
   # Check if ChromaDB is available
  if not manager.retriever.is_available():
      print("\n❌ ChromaDB not available!")
      print(f"   Checked: {config.chroma_dir}")
      print("\n  Make sure:")
      print("   1. GangDan has indexed some documents")
      print("   2. ChromaDB directory exists")
       return False
    
  print("\n✅ ChromaDB connected successfully")
    
   # List available KBs
  print("\n📚 Available Knowledge Bases:")
  kbs = manager.list_kbs()
    
  if not kbs:
      print("   No KBs found. Please index documents first.")
       return False
    
  for i, kb in enumerate(kbs[:10], 1):  # Show first 10
       doc_count = kb.get('doc_count', 'unknown')
      print(f"   {i}. {kb['name']} ({doc_count} docs)")
    
  if len(kbs) > 10:
      print(f"   ... and {len(kbs) - 10} more")
    
   return True


def demo_search(manager, query):
   """Demonstrate KB search."""
  print(f"\n🔍 Searching for: \"{query}\"")
    
   # Search and synthesize
  context, sources = manager.search_and_synthesize(
       query,
      max_chars=2000,  # Limit context length for demo
   )
    
  if not sources:
      print("   ❌ No relevant content found")
       return
    
  print(f"   ✅ Found {len(sources)} source(s):")
  for source in sources:
      print(f"      - {source}")
    
  print(f"\n  Context preview ({len(context)} chars):")
  print("   " + "-" * 55)
    
   # Show preview
  preview = context[:500] + "..." if len(context) > 500 else context
  for line in preview.split('\n'):
      print(f"   {line}")
    
  print("   " + "-" * 55)


def demo_strict_mode():
   """Demonstrate strict KB mode."""
  print("\n" + "=" * 60)
  print("Strict KB Mode Demo")
  print("=" * 60)
    
  config = KBConfig(
       chroma_dir=str(Path.home() / "GangDan" / "data" / "chroma"),
     embedding_model="nomic-embed-text",
      ollama_url="http://localhost:11434",
      strict_kb_mode=True,  # Enable strict mode
   )
    
  manager = KBManager(config)
    
  print(f"\nStrict mode enabled: {manager.is_strict_mode()}")
  print("\nIn strict mode, the system will refuse to answer")
  print("questions when no relevant KB content is found.")


def demo_multi_kb():
   """Demonstrate multi-KB synthesis."""
  print("\n" + "=" * 60)
  print("Multi-KB Synthesis Demo")
  print("=" * 60)
    
  config = KBConfig(
       chroma_dir=str(Path.home() / "GangDan" / "data" / "chroma"),
     embedding_model="nomic-embed-text",
      ollama_url="http://localhost:11434",
   )
    
  manager = KBManager(config)
    
   # List available KBs
  kbs = manager.list_kbs()
  kb_names = [kb['name'] for kb in kbs[:5]]  # Use first 5
    
  if len(kb_names) < 2:
      print("\nNeed at least 2 KBs for multi-KB demo")
       return
    
  print(f"\nAvailable KBs: {', '.join(kb_names)}")
    
   # Search specific KBs
  selected = kb_names[:2]
  print(f"\nSearching only: {', '.join(selected)}")
    
   query = "array operations" if 'numpy' in str(selected).lower() else"operations"
  context, sources = manager.search_and_synthesize(
       query,
      collections=selected,
   )
    
  print(f"\n✅ Synthesized from {len(sources)} source(s)")
  if sources:
      print(f"   Sources: {', '.join(sources)}")


def main():
   """Run all demos."""
  print("\n" + "=" * 60)
  print("  Liao KB Integration with GangDan Compatibility")
  print("=" * 60)
    
   # Demo 1: Basic usage
  if demo_basic_usage():
      config = KBConfig(
           chroma_dir=str(Path.home() / "GangDan" / "data" / "chroma"),
         embedding_model="nomic-embed-text",
          ollama_url="http://localhost:11434",
       )
      manager = KBManager(config)
        
       # Demo searches
      demo_search(manager, "NumPy arrays")
      demo_search(manager, "pandas DataFrame")
        
       # Demo other features
      demo_strict_mode()
      demo_multi_kb()
  else:
      print("\n⚠️  Skipping search demos (ChromaDB not available)")
    
  print("\n" + "=" * 60)
  print("Demo Complete!")
  print("=" * 60)
  print("\nFor more information, see:")
  print("  - KB_INTEGRATION.md")
  print("  - KB_IMPLEMENTATION_SUMMARY.md")
  print("\n")


if __name__ == "__main__":
   try:
      main()
   except KeyboardInterrupt:
      print("\n\nInterrupted by user")
       sys.exit(0)
   except Exception as e:
      print(f"\n❌ Error: {e}")
       import traceback
       traceback.print_exc()
       sys.exit(1)
