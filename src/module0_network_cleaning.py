# module0_network_cleaning.py - Base Network Schema Sanitisation
import os

class NetworkPreparer:
    """
    Acts as the initial gatekeeper for the UAM Scenario Toolkit (UST).
    Inspects raw network XML files and strictly enforces the MATSim DTD schema
    prior to native Java SAX parsing to prevent NullPointerExceptions.
    """
    def __init__(self):
        pass

    def enforce_matsim_header(self, input_path, output_path):
        print("--- Module 0: Network Preparer Initiated ---")
        print(f"[NetworkPreparer] Inspecting raw network file: {input_path}")
        
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Raw network file not found at: {input_path}")
            
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if the mandatory MATSim schema is present
        if "<!DOCTYPE network" not in content:
            print("[NetworkPreparer] WARNING: Missing MATSim DTD Header. Injecting standard MATSim v2 schema...")
            
            # Safely inject the DTD header immediately after the XML declaration
            if "<?xml" in content:
                end_idx = content.find("?>") + 2
                new_content = content[:end_idx] + '\n<!DOCTYPE network SYSTEM "http://www.matsim.org/files/dtd/network_v2.dtd">' + content[end_idx:]
            else:
                new_content = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE network SYSTEM "http://www.matsim.org/files/dtd/network_v2.dtd">\n' + content
                
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"[NetworkPreparer] Header successfully injected. Prepped network saved to: {output_path}\n")
        else:
            print("[NetworkPreparer] Valid MATSim DTD Header detected. No injection required.\n")
            if input_path != output_path:
                import shutil
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                shutil.copy(input_path, output_path)

if __name__ == "__main__":
    prep = NetworkPreparer()
    # Default testing paths
    prep.enforce_matsim_header("../data/base_network.xml", "../scenarios/networks/base_network_prepped.xml")