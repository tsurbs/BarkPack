import sys
import os

def test_weasyprint():
    print("Checking WeasyPrint...")
    try:
        from weasyprint import HTML
        print("✅ WeasyPrint imported successfully.")
        
        # Try a simple PDF generation
        print("Attempting to generate a simple PDF...")
        html = HTML(string="<h1>Hello WeasyPrint</h1>")
        pdf_bytes = html.write_pdf()
        
        output_path = "/tmp/weasyprint_test.pdf"
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        
        print(f"✅ PDF generated successfully at {output_path}")
        print(f"   Size: {len(pdf_bytes)} bytes")
        return True
    except ImportError as e:
        print(f"❌ ImportError: {e}")
        print("\nPossible missing libraries for WeasyPrint:")
        print("- libpango-1.0-0")
        print("- libharfbuzz0b")
        print("- libpangoft2-1.0-0")
        print("- libpangocairo-1.0-0")
        print("- libglib2.0-0")
        print("- libffi-dev")
        print("- shared-mime-info")
        return False
    except Exception as e:
        print(f"❌ An error occurred: {e}")
        return False

if __name__ == "__main__":
    success = test_weasyprint()
    sys.exit(0 if success else 1)
