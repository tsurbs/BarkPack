"""
PDF Generation Tools for Bark Bot.
Uses WeasyPrint to convert HTML to PDF.
"""
import os
import uuid
from typing import Optional
from pydantic import BaseModel, Field
from app.tools.base import BaseTool
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession


class GeneratePDFArgs(BaseModel):
    """Arguments for PDF generation."""
    html_content: str = Field(
        description="The HTML content to convert to PDF. Can include CSS styling in <style> tags or inline styles."
    )
    filename: str = Field(
        description="Optional output filename (e.g. 'report.pdf'). Defaults to a generated name.",
        default=None,
    )
    base_url: str = Field(
        description="Optional base URL for resolving relative links in the HTML. Defaults to file:///tmp/.",
        default=None,
    )


class GeneratePDFTool(BaseTool):
    """Tool to generate PDFs from HTML using WeasyPrint."""
    name = "generate_pdf"
    description = (
        "Generate a PDF document from HTML content using WeasyPrint. "
        "The PDF will be saved to /tmp and attached to your response. "
        "This tool accepts raw HTML content, which can include embedded CSS in <style> tags or inline styles. "
        "Best for creating reports, invoices, documents, and any formatted content. "
        "Returns an attachment directive so the PDF can be shared in chat."
    )
    args_schema = GeneratePDFArgs

    async def run(self, args: GeneratePDFArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        """
        Generate a PDF from HTML content using WeasyPrint.
        
        Args:
            args: GeneratePDFArgs containing html_content, optional filename, and base_url
            user: The user making the request
            db: Optional database session
            
        Returns:
            Attachment directive string or error message
        """
        try:
            from weasyprint import HTML

            # Generate filename if not provided
            if not args.filename:
                filename = f"document_{uuid.uuid4().hex[:8]}.pdf"
            else:
                # Ensure .pdf extension
                filename = args.filename
                if not filename.lower().endswith('.pdf'):
                    filename = f"{filename}.pdf"
            
            # Set base URL for resolving relative paths
            base_url = args.base_url or "file:///tmp/"
            
            # Create PDF using WeasyPrint
            html = HTML(string=args.html_content, base_url=base_url)
            
            # Generate PDF bytes
            pdf_bytes = html.write_pdf()
            
            # Save to /tmp
            file_path = os.path.join("/tmp", filename)
            with open(file_path, "wb") as f:
                f.write(pdf_bytes)
            
            # Return attachment directive for the response handler
            return f"__ATTACHMENT__|||{file_path}|||{filename}"
            
        except Exception as e:
            return f"Error generating PDF: {str(e)}"


class GeneratePDFWithURLArgs(BaseModel):
    """Arguments for PDF generation from URL."""
    url: str = Field(
        description="The URL to fetch and convert to PDF."
    )
    filename: str = Field(
        description="Optional output filename (e.g. 'webpage.pdf'). Defaults to a generated name.",
        default=None,
    )


class GeneratePDFWithURLTool(BaseTool):
    """Tool to generate PDFs from a URL using WeasyPrint."""
    name = "generate_pdf_from_url"
    description = (
        "Generate a PDF from a URL by fetching the webpage and converting it using WeasyPrint. "
        "The PDF will be saved to /tmp and attached to your response. "
        "Best for capturing web pages as PDF documents. "
        "Returns an attachment directive so the PDF can be shared in chat."
    )
    args_schema = GeneratePDFWithURLArgs

    async def run(self, args: GeneratePDFWithURLArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        """
        Generate a PDF from a URL using WeasyPrint.
        
        Args:
            args: GeneratePDFWithURLArgs containing url and optional filename
            user: The user making the request
            db: Optional database session
            
        Returns:
            Attachment directive string or error message
        """
        try:
            from weasyprint import HTML

            # Generate filename if not provided
            if not args.filename:
                filename = f"webpage_{uuid.uuid4().hex[:8]}.pdf"
            else:
                # Ensure .pdf extension
                filename = args.filename
                if not filename.lower().endswith('.pdf'):
                    filename = f"{filename}.pdf"
            
            # Create PDF from URL using WeasyPrint
            html = HTML(url=args.url)
            
            # Generate PDF bytes
            pdf_bytes = html.write_pdf()
            
            # Save to /tmp
            file_path = os.path.join("/tmp", filename)
            with open(file_path, "wb") as f:
                f.write(pdf_bytes)
            
            # Return attachment directive for the response handler
            return f"__ATTACHMENT__|||{file_path}|||{filename}"
            
        except Exception as e:
            return f"Error generating PDF from URL: {str(e)}"
