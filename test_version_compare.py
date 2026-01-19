
def check_version(current, remote):
    print(f"Current: {current}, Remote: {remote}")
    if remote and remote != current:
        print("Result: Update Available (Inequality Check)")
    else:
        print("Result: No Update")

print("--- Current Logic Test ---")
check_version("26.0.1", "26.0.2") # Should be Update
check_version("26.0.1", "26.0.0") # Should NOT be Update (Downgrade)
check_version("26.0.1", "26.0.1") # No Update

def improved_check(current, remote):
    print(f"Current: {current}, Remote: {remote}")
    try:
        # Simple semantic split
        c_parts = [int(x) for x in current.split('.')]
        r_parts = [int(x) for x in remote.split('.')]
        
        if r_parts > c_parts:
             print("Result: Update Available (Semantic Check)")
        else:
             print("Result: No Update")
    except:
        # Fallback
        if remote != current:
             print("Result: Update Available (Fallback)")
        else:
             print("Result: No Update")

print("\n--- Improved Logic Test ---")
improved_check("26.0.1", "26.0.2")
improved_check("26.0.1", "26.0.0")
improved_check("26.0.1", "26.0.1")
