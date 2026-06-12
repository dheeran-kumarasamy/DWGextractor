import streamlit as st
import ezdxf
import subprocess
import tempfile
import shutil
import os
from pathlib import Path
import json
from datetime import datetime

st.set_page_config(page_title="CAD Template Matcher", layout="wide")

st.title("🏗️ CAD Template Matcher")
st.markdown("Upload a CAD diagram and match it against a standard template.")

# Initialize session state
if 'validation_results' not in st.session_state:
    st.session_state.validation_results = None
if 'template_file' not in st.session_state:
    st.session_state.template_file = None
if 'user_file' not in st.session_state:
    st.session_state.user_file = None

def extract_dxf_info(dxf_bytes):
    """Extract layers and objects from DXF file"""
    try:
        # ezdxf can read from a filename or bytes; prefer reading from bytes-like
        try:
            doc = ezdxf.readbytes(dxf_bytes)
        except Exception:
            # Fallback: write to a temp file and read
            tf = tempfile.NamedTemporaryFile(delete=False, suffix='.dxf')
            tf.write(dxf_bytes)
            tf.close()
            doc = ezdxf.readfile(tf.name)
            os.unlink(tf.name)
        
        # Extract layers
        layers = []
        for layer in doc.layers:
            if layer.dxf.name != "0":  # Skip default layer
                layers.append({
                    'name': layer.dxf.name,
                    'color': layer.dxf.color,
                    'linetype': layer.dxf.linetype,
                })
        
        # Extract objects/entities
        objects = {
            'LINE': 0,
            'CIRCLE': 0,
            'ARC': 0,
            'LWPOLYLINE': 0,
            'POLYLINE': 0,
            'TEXT': 0,
            'DIMENSION': 0,
            'INSERT': 0,  # Blocks
            'POINT': 0,
            'SPLINE': 0,
        }
        
        entity_details = {}
        for entity in doc.modelspace().query('*'):
            entity_type = entity.dxf.entity_type
            if entity_type in objects:
                objects[entity_type] += 1
                if entity_type not in entity_details:
                    entity_details[entity_type] = []
                # Store basic entity info
                entity_details[entity_type].append({
                    'layer': entity.dxf.layer if hasattr(entity.dxf, 'layer') else 'N/A',
                    'color': entity.dxf.color if hasattr(entity.dxf, 'color') else 256,
                })
        
        return {
            'success': True,
            'layers': layers,
            'objects': {k: v for k, v in objects.items() if v > 0},
            'object_details': entity_details,
            'total_entities': len(list(doc.modelspace()))
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def convert_dwg_to_dxf(dwg_path):
    """Attempt to convert a DWG file to DXF using an available converter.
    Tries `dwg2dxf` if present. Returns path to created DXF or (None, error_msg).
    """
    dxf_path = dwg_path + '.converted.dxf'

    # Try dwg2dxf
    dwg2dxf = shutil.which('dwg2dxf')
    if dwg2dxf:
        try:
            res = subprocess.run([dwg2dxf, dwg_path, dxf_path], check=True, capture_output=True)
            if os.path.exists(dxf_path):
                return dxf_path, None
            return None, 'Converter ran but output DXF not found.'
        except subprocess.CalledProcessError as e:
            return None, f'dwg2dxf failed: {e.stderr.decode(errors="ignore")}'

    # Try ODAFileConverter if available (simple heuristic)
    oda = shutil.which('ODAFileConverter') or shutil.which('oda_file_converter')
    if oda:
        # ODAFileConverter generally works on folders; create temp dirs
        in_dir = tempfile.mkdtemp()
        out_dir = tempfile.mkdtemp()
        try:
            shutil.copy(dwg_path, in_dir)
            # The exact args for ODAFileConverter vary across versions; try a common pattern
            try:
                subprocess.run([oda, in_dir, out_dir, 'ACAD2013', 'DXF', '0', '0', '0'], check=True, capture_output=True)
            except Exception:
                # best-effort: run without args
                subprocess.run([oda, in_dir, out_dir], check=True, capture_output=True)
            # find a DXF in out_dir
            for f in os.listdir(out_dir):
                if f.lower().endswith('.dxf'):
                    return os.path.join(out_dir, f), None
            return None, 'ODA converter ran but no DXF produced.'
        finally:
            pass

    return None, 'No DWG→DXF converter found on the system. Install `dwg2dxf` or ODA File Converter.'

def compare_templates(template_info, user_info):
    """Compare template with user CAD"""
    results = {
        'match_status': 'GOOD',
        'issues': [],
        'matches': [],
        'layer_comparison': {},
        'object_comparison': {},
    }
    
    # Compare layers
    template_layers = {l['name']: l for l in template_info['layers']}
    user_layers = {l['name']: l for l in user_info['layers']}
    
    for layer_name, layer_info in template_layers.items():
        if layer_name in user_layers:
            results['matches'].append(f"✓ Layer '{layer_name}' present")
            results['layer_comparison'][layer_name] = 'MATCH'
        else:
            results['issues'].append(f"✗ Missing layer: '{layer_name}'")
            results['match_status'] = 'NEEDS_REVIEW'
            results['layer_comparison'][layer_name] = 'MISSING'
    
    # Check for extra layers in user file
    for layer_name in user_layers:
        if layer_name not in template_layers:
            results['matches'].append(f"⚠ Extra layer in user file: '{layer_name}'")
            results['layer_comparison'][layer_name] = 'EXTRA'
    
    # Compare objects
    template_objects = template_info['objects']
    user_objects = user_info['objects']
    
    for obj_type, count in template_objects.items():
        user_count = user_objects.get(obj_type, 0)
        if user_count > 0:
            results['matches'].append(f"✓ {obj_type}: {user_count} objects (expected {count})")
            results['object_comparison'][obj_type] = f"{user_count}/{count}"
        else:
            results['issues'].append(f"✗ Missing {obj_type} objects (expected {count})")
            results['match_status'] = 'NEEDS_REVIEW'
            results['object_comparison'][obj_type] = f"0/{count}"
    
    return results

# Sidebar for template selection
st.sidebar.header("📋 Template Configuration")
template_option = st.sidebar.radio(
    "Template Source:",
    ["Upload Template", "Use Default Path"]
)

template_info = None

if template_option == "Upload Template":
    template_file = st.sidebar.file_uploader("Upload Template (DXF or DWG)", type=['dxf', 'dwg'], key='template_upload')
    if template_file:
        tname = template_file.name
        if tname.lower().endswith('.dwg'):
            tf = tempfile.NamedTemporaryFile(delete=False, suffix='.dwg')
            tf.write(template_file.read())
            tf.close()
            st.sidebar.info("DWG template uploaded — attempting conversion to DXF...")
            dxf_path, err = convert_dwg_to_dxf(tf.name)
            if dxf_path:
                with open(dxf_path, 'rb') as f:
                    template_info = extract_dxf_info(f.read())
                st.session_state.template_file = tname + ' (converted)'
            else:
                st.sidebar.error(f"DWG conversion failed: {err}")
        else:
            template_info = extract_dxf_info(template_file.read())
            st.session_state.template_file = template_file.name
else:
    default_template_path = "/Users/sindhujachandrasekar/Documents/cad2entity/LibreCAD/templates"
    if os.path.exists(default_template_path):
        dxf_files = [f for f in os.listdir(default_template_path) if f.endswith('.dxf')]
        if dxf_files:
            selected_template = st.sidebar.selectbox("Select Template:", dxf_files)
            template_path = os.path.join(default_template_path, selected_template)
            with open(template_path, 'rb') as f:
                template_info = extract_dxf_info(f.read())
            st.session_state.template_file = selected_template
        else:
            st.sidebar.warning("No DXF templates found in default path")
    else:
        st.sidebar.info(f"Create templates at: {default_template_path}")

# Main content area
col1, col2 = st.columns(2)

with col1:
    st.header("Template")
    if template_info and template_info.get('success'):
        st.success(f"Template loaded: {st.session_state.template_file}")
        
        with st.expander("📊 Template Details", expanded=True):
            st.subheader("Layers")
            for layer in template_info['layers']:
                st.text(f"  • {layer['name']} (Color: {layer['color']})")
            
            st.subheader("Objects")
            for obj_type, count in template_info['objects'].items():
                st.text(f"  • {obj_type}: {count}")
            
            st.metric("Total Entities", template_info['total_entities'])
    else:
        st.info("Upload or select a template to begin")

with col2:
    st.header("User CAD File")
    user_file = st.file_uploader("Upload your CAD diagram (DXF or DWG)", type=['dxf', 'dwg'], key='user_upload')
    user_info = None
    
    if user_file:
        filename = user_file.name
        # Handle DWG by attempting conversion
        if filename.lower().endswith('.dwg'):
            tf = tempfile.NamedTemporaryFile(delete=False, suffix='.dwg')
            tf.write(user_file.read())
            tf.close()
            st.info("DWG uploaded — attempting to convert to DXF...")
            dxf_path, err = convert_dwg_to_dxf(tf.name)
            if dxf_path:
                with open(dxf_path, 'rb') as f:
                    user_info = extract_dxf_info(f.read())
                st.session_state.user_file = filename + ' (converted)'
                st.success(f"DWG converted to DXF: {os.path.basename(dxf_path)}")
            else:
                st.error(f"DWG conversion failed: {err}")
                st.info("Install a DWG→DXF converter (e.g. ODA File Converter or dwg2dxf), or convert using LibreCAD and re-upload a DXF.")
        else:
            user_info = extract_dxf_info(user_file.read())
            st.session_state.user_file = filename
        
        if user_info:
            if user_info.get('success'):
                st.success(f"File loaded: {filename}")
                
                with st.expander("📊 Your File Details", expanded=True):
                    st.subheader("Layers")
                    for layer in user_info['layers']:
                        st.text(f"  • {layer['name']} (Color: {layer['color']})")
                    
                    st.subheader("Objects")
                    for obj_type, count in user_info['objects'].items():
                        st.text(f"  • {obj_type}: {count}")
                    
                    st.metric("Total Entities", user_info['total_entities'])
            else:
                st.error(f"Error reading file: {user_info.get('error')}")

# Comparison section
st.divider()
st.header("🔍 Template Matching Analysis")

if template_info and template_info.get('success') and user_file and user_info and user_info.get('success'):
    results = compare_templates(template_info, user_info)
    
    # Status indicator
    if results['match_status'] == 'GOOD':
        st.success("✅ **MATCH STATUS: GOOD** - CAD file matches template requirements")
    else:
        st.warning("⚠️ **MATCH STATUS: NEEDS REVIEW** - Some differences found")
    
    # Results in columns
    result_col1, result_col2 = st.columns(2)
    
    with result_col1:
        st.subheader("✓ Matches")
        for match in results['matches']:
            st.text(match)
    
    with result_col2:
        st.subheader("✗ Issues")
        if results['issues']:
            for issue in results['issues']:
                st.text(issue)
        else:
            st.success("No issues found!")
    
    # Detailed comparison tables
    st.subheader("Layer Comparison")
    layer_data = []
    for layer_name, status in results['layer_comparison'].items():
        layer_data.append({
            'Layer Name': layer_name,
            'Status': status,
            '✓': '✓' if status == 'MATCH' else '✗'
        })
    st.dataframe(layer_data, use_container_width=True)
    
    st.subheader("Object Type Comparison")
    object_data = []
    for obj_type, comparison in results['object_comparison'].items():
        user_count, expected_count = comparison.split('/')
        object_data.append({
            'Object Type': obj_type,
            'Your Count': int(user_count),
            'Expected': int(expected_count),
            'Match': '✓' if user_count == expected_count else '⚠'
        })
    st.dataframe(object_data, use_container_width=True)
    
    # Submission section
    st.divider()
    st.header("📤 Submit Results")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col2:
        if st.button("✓ Submit", key='submit_btn', use_container_width=True):
            submission = {
                'timestamp': datetime.now().isoformat(),
                'template_file': st.session_state.template_file,
                'user_file': st.session_state.user_file,
                'match_status': results['match_status'],
                'layers_matched': sum(1 for s in results['layer_comparison'].values() if s == 'MATCH'),
                'layers_total': len(results['layer_comparison']),
                'issues': results['issues'],
            }
            
            # Save submission
            submissions_dir = "submissions"
            os.makedirs(submissions_dir, exist_ok=True)
            submission_file = os.path.join(submissions_dir, f"submission_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(submission_file, 'w') as f:
                json.dump(submission, f, indent=2)
            
            st.success(f"✅ Submission saved to {submission_file}")
            st.balloons()
            
            # Show submission details
            with st.expander("Submission Details"):
                st.json(submission)
    
    with col3:
        if st.button("Reset", key='reset_btn', use_container_width=True):
            st.session_state.validation_results = None
            st.session_state.template_file = None
            st.session_state.user_file = None
            st.rerun()

else:
    st.info("📝 Upload both a template and your CAD file to begin matching.")

# Footer
st.divider()
st.markdown("""
**How to use:**
1. Select or upload a DXF template file
2. Upload your CAD diagram (DXF format)
3. Review the layer and object comparisons
4. Submit when validated

**Supported file format:** DXF (Drawing Exchange Format)
**Note:** For DWG files, convert to DXF first using LibreCAD or similar tools.
""")
