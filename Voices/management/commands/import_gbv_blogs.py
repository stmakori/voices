import os
from docx import Document
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils.text import slugify
from Voices.models import Blog
from PIL import Image as PILImage
from io import BytesIO


class Command(BaseCommand):
    help = 'Extract and import 10 GBV educational blogs from GBV_Blog_Series.docx'

    def handle(self, *args, **options):
        docx_path = 'GBV_Blog_Series.docx'
        
        if not os.path.exists(docx_path):
            self.stdout.write(self.style.ERROR(f'File not found: {docx_path}'))
            return

        # Load the docx document
        doc = Document(docx_path)
        
        # Extract blogs
        blogs_data = self._extract_blogs_from_docx(doc)
        
        self.stdout.write(self.style.SUCCESS(f'Extracted {len(blogs_data)} blogs from document'))
        
        # Get image directory
        image_dir = 'imag'
        
        # Create or update blogs in database
        for idx, blog_data in enumerate(blogs_data, 1):
            self._create_or_update_blog(blog_data, idx, image_dir)
        
        self.stdout.write(self.style.SUCCESS('Blog import completed successfully!'))

    def _extract_blogs_from_docx(self, doc):
        """Extract blogs from the docx document with proper heading structure."""
        blogs = []
        current_blog = None
        current_content = []
        
        # Blog categories mapping - only exact matches are category headers
        category_headers = ['UNDERSTANDING GBV', 'PREVENTION', 'SUPPORT SERVICES', 'LEGAL RIGHTS', 'RECOVERY AND HEALING']
        category_map = {
            'UNDERSTANDING GBV': 'awareness',
            'PREVENTION': 'prevention',
            'SUPPORT SERVICES': 'support',
            'LEGAL RIGHTS': 'legal',
            'RECOVERY': 'recovery',
        }
        
        for para in doc.paragraphs:
            text = para.text.strip()
            
            if not text:
                continue
            
            # Check if this is a blog title (Heading 1 style)
            is_heading = para.style and para.style.name == "Heading 1"
            
            # Check if this is a section heading (Heading 2 style)
            is_heading2 = para.style and para.style.name == "Heading 2"
            
            # Check if this is exactly a category header (entire line matches)
            is_category_header = text.upper() in category_headers or any(
                text.upper() == cat for cat in category_headers
            )
            
            # Check if paragraph contains blog number indicator
            is_blog_marker = 'Blog' in text and 'of 10' in text
            
            if is_heading and not is_category_header and not is_blog_marker:
                # Save previous blog if exists
                if current_blog:
                    current_blog['content'] = '\n\n'.join(current_content).strip()
                    blogs.append(current_blog)
                
                # Start new blog - determine category from adjacent text
                current_blog = {
                    'title': text,
                    'content': '',
                    'category': 'awareness',
                }
                current_content = []
            
            elif current_blog is not None:
                # Determine category from text
                upper_text = text.upper()
                for cat_key, cat_value in category_map.items():
                    if cat_key in upper_text:
                        current_blog['category'] = cat_value
                        break
                
                # Add content to current blog with proper formatting
                if text and not is_blog_marker and not is_category_header:
                    # Convert Heading 2 to h2 markup for proper formatting
                    if is_heading2:
                        current_content.append(f'<h2>{text}</h2>')
                    else:
                        current_content.append(f'<p>{text}</p>')
        
        # Don't forget the last blog
        if current_blog:
            # Wrap paragraphs in proper HTML tags and join
            content_html = '\n'.join(current_content).strip()
            current_blog['content'] = content_html
            blogs.append(current_blog)
        
        return blogs[:10]  # Ensure only 10 blogs

    def _create_or_update_blog(self, blog_data, blog_number, image_dir):
        """Create or update a blog in the database."""
        title = blog_data['title']
        content = blog_data['content']
        category = blog_data['category']
        
        # Calculate read time (approximate: 200 words per minute)
        word_count = len(content.split())
        read_time = max(1, word_count // 200)
        
        # Get or create the blog
        blog, created = Blog.objects.update_or_create(
            title=title,
            defaults={
                'content': content,
                'category': category,
                'read_time': read_time,
                'published': True,
                'views': 0,
            }
        )
        
        # Attach image if it exists
        image_name = f'blog {blog_number}.jpeg'
        image_path = os.path.join(image_dir, image_name)
        
        # Also check for .png variant
        if not os.path.exists(image_path):
            image_path = os.path.join(image_dir, f'blog {blog_number}.png')
        
        if os.path.exists(image_path):
            try:
                # Open and process the image
                with open(image_path, 'rb') as img_file:
                    img_content = img_file.read()
                
                # Save image to the blog
                blog.image.save(
                    f'blog_{blog_number}.jpg',
                    ContentFile(img_content),
                    save=True
                )
                status = 'created' if created else 'updated'
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Blog {blog_number}: {title} ({status}, with image)')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'  ⚠ Blog {blog_number}: {title} ({created and "created" or "updated"}, image error: {str(e)})')
                )
        else:
            status = 'created' if created else 'updated'
            self.stdout.write(
                self.style.WARNING(f'  ⚠ Blog {blog_number}: {title} ({status}, no image found)')
            )
