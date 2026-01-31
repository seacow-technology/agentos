"""
Example: Using Capability Registry and Audit System

This example demonstrates common usage patterns for the Capability Registry
and Audit System in AgentOS.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agentos.core.capability_registry import get_capability_registry
from agentos.core.audit import (
    log_audit_event,
    get_audit_events,
    SNIPPET_CREATED,
    PREVIEW_SESSION_CREATED,
    PREVIEW_DEP_INJECTED,
)


def example_1_list_capabilities():
    """Example 1: List all available capabilities"""
    print("\n" + "="*60)
    print("Example 1: List All Capabilities")
    print("="*60)

    registry = get_capability_registry()
    capabilities = registry.list_all()

    print(f"\nFound {len(capabilities)} capabilities:\n")
    for cap in capabilities:
        print(f"ID: {cap.capability_id}")
        print(f"  Name: {cap.name}")
        print(f"  Kind: {cap.kind.value}")
        print(f"  Risk Level: {cap.risk_level.value}")
        print(f"  Audit Events: {', '.join(cap.audit_events)}")
        if cap.presets:
            print(f"  Presets: {len(cap.presets)} available")
        print()


def example_2_explore_presets():
    """Example 2: Explore preview runtime presets"""
    print("\n" + "="*60)
    print("Example 2: Explore Preview Presets")
    print("="*60)

    registry = get_capability_registry()
    preview_cap = registry.get("preview")

    print(f"\nPreview capability has {len(preview_cap.presets)} presets:\n")
    for preset in preview_cap.presets:
        print(f"Preset: {preset.id}")
        print(f"  Name: {preset.name}")
        print(f"  Description: {preset.description}")
        print(f"  Dependencies: {len(preset.dependencies)}")

        core_deps = preset.get_core_deps()
        optional_deps = preset.get_optional_deps()

        if core_deps:
            print(f"  Core: {[d.id for d in core_deps]}")
        if optional_deps:
            print(f"  Optional: {[d.id for d in optional_deps]}")

        print()


def example_3_detect_dependencies():
    """Example 3: Smart dependency detection for Three.js"""
    print("\n" + "="*60)
    print("Example 3: Smart Dependency Detection")
    print("="*60)

    registry = get_capability_registry()
    three_preset = registry.get_preset("preview", "three-webgl-umd")

    # Test case 1: Basic Three.js
    code1 = """
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer();
    """

    deps1 = registry.detect_required_deps(three_preset, code1)
    print("\nTest 1: Basic Three.js scene")
    print(f"Code: {code1.strip()[:80]}...")
    print(f"Dependencies: {[d.id for d in deps1]}")

    # Test case 2: With OrbitControls
    code2 = """
    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.update();
    """

    deps2 = registry.detect_required_deps(three_preset, code2)
    print("\nTest 2: With OrbitControls")
    print(f"Code: {code2.strip()[:80]}...")
    print(f"Dependencies: {[d.id for d in deps2]}")

    # Test case 3: Multiple features
    code3 = """
    const loader = new THREE.FontLoader();
    loader.load('font.json', function(font) {
        const geometry = new THREE.TextGeometry('Hello', {
            font: font,
            size: 80,
            height: 5,
        });
    });

    const controls = new THREE.OrbitControls(camera);
    """

    deps3 = registry.detect_required_deps(three_preset, code3)
    print("\nTest 3: Multiple features (Font + Text + Controls)")
    print(f"Code: {code3.strip()[:80]}...")
    print(f"Dependencies: {[d.id for d in deps3]}")


def example_4_log_audit_events():
    """Example 4: Log various audit events"""
    print("\n" + "="*60)
    print("Example 4: Logging Audit Events")
    print("="*60)

    # Log snippet creation
    print("\nLogging snippet creation...")
    snippet_id = "example-snippet-001"
    audit_id1 = log_audit_event(
        event_type=SNIPPET_CREATED,
        snippet_id=snippet_id,
        metadata={
            "language": "javascript",
            "size": 256,
            "source": "chat",
            "session_id": "chat-session-123"
        }
    )
    print(f"✓ Created audit record {audit_id1} for snippet {snippet_id}")

    # Log preview session
    print("\nLogging preview session creation...")
    preview_id = "example-preview-001"
    audit_id2 = log_audit_event(
        event_type=PREVIEW_SESSION_CREATED,
        preview_id=preview_id,
        snippet_id=snippet_id,
        metadata={
            "preset": "three-webgl-umd",
            "ttl": 3600,
        }
    )
    print(f"✓ Created audit record {audit_id2} for preview {preview_id}")

    # Log dependency injection
    print("\nLogging dependency injection...")
    audit_id3 = log_audit_event(
        event_type=PREVIEW_DEP_INJECTED,
        preview_id=preview_id,
        metadata={
            "dep_id": "three-orbit-controls",
            "reason": "OrbitControls detected in code",
            "auto_injected": True,
        }
    )
    print(f"✓ Created audit record {audit_id3} for dependency injection")


def example_5_query_audit_events():
    """Example 5: Query audit events"""
    print("\n" + "="*60)
    print("Example 5: Querying Audit Events")
    print("="*60)

    # Query by snippet
    print("\nQuerying events for snippet 'example-snippet-001'...")
    events = get_audit_events(snippet_id="example-snippet-001", limit=10)
    print(f"Found {len(events)} events:\n")

    for event in events:
        print(f"  [{event['event_type']}] at {event['created_at']}")
        print(f"    Task: {event['task_id']}")
        if event['payload']:
            print(f"    Payload: {event['payload']}")
        print()


def example_6_complete_workflow():
    """Example 6: Complete workflow simulation"""
    print("\n" + "="*60)
    print("Example 6: Complete Workflow Simulation")
    print("="*60)

    print("\nSimulating a complete workflow:")
    print("1. User creates Three.js code in chat")
    print("2. Code is saved as snippet")
    print("3. Preview session is created")
    print("4. Dependencies are auto-injected")
    print("5. User views preview")

    registry = get_capability_registry()

    # Step 1: User code
    user_code = """
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera();
    const renderer = new THREE.WebGLRenderer();

    const controls = new THREE.OrbitControls(camera, renderer.domElement);

    const geometry = new THREE.BoxGeometry();
    const material = new THREE.MeshBasicMaterial({ color: 0x00ff00 });
    const cube = new THREE.Mesh(geometry, material);
    scene.add(cube);

    function animate() {
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    }
    animate();
    """

    print(f"\n✓ User code: {len(user_code)} characters")

    # Step 2: Save snippet
    snippet_id = "workflow-snippet-001"
    log_audit_event(
        event_type=SNIPPET_CREATED,
        snippet_id=snippet_id,
        metadata={"language": "javascript", "source": "chat"}
    )
    print(f"✓ Snippet saved: {snippet_id}")

    # Step 3: Detect dependencies
    three_preset = registry.get_preset("preview", "three-webgl-umd")
    deps = registry.detect_required_deps(three_preset, user_code)
    print(f"✓ Dependencies detected: {[d.id for d in deps]}")

    # Step 4: Create preview session
    preview_id = "workflow-preview-001"
    log_audit_event(
        event_type=PREVIEW_SESSION_CREATED,
        preview_id=preview_id,
        snippet_id=snippet_id,
        metadata={
            "preset": three_preset.id,
            "deps_detected": [d.id for d in deps],
        }
    )
    print(f"✓ Preview session created: {preview_id}")

    # Step 5: Log each dependency injection
    for dep in deps:
        if dep.condition:  # Only log optional deps
            log_audit_event(
                event_type=PREVIEW_DEP_INJECTED,
                preview_id=preview_id,
                metadata={
                    "dep_id": dep.id,
                    "dep_url": dep.url,
                    "auto_injected": True,
                }
            )
            print(f"  ✓ Auto-injected: {dep.id}")

    # Step 6: Query complete audit trail
    print("\n✓ Complete audit trail:")
    events = get_audit_events(preview_id=preview_id)
    for event in events:
        print(f"  - {event['event_type']}")

    print("\n✅ Workflow completed successfully!")


def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("Capability Registry & Audit System Examples")
    print("="*60)

    example_1_list_capabilities()
    example_2_explore_presets()
    example_3_detect_dependencies()
    example_4_log_audit_events()
    example_5_query_audit_events()
    example_6_complete_workflow()

    print("\n" + "="*60)
    print("All examples completed successfully!")
    print("="*60)
    print("\nNext steps:")
    print("1. Integrate with Preview API (agentos/webui/api/preview.py)")
    print("2. Integrate with Snippets API (agentos/webui/api/snippets.py)")
    print("3. Add frontend UI for preset selection")
    print("4. Implement task materialization")
    print()


if __name__ == "__main__":
    main()
