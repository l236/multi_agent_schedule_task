"""
Document parsing tool.
"""

import os
import logging
import email
import mimetypes
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..tools import BaseTool

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False

try:
    from imapclient import IMAPClient
    HAS_IMAPCLIENT = True
except ImportError:
    HAS_IMAPCLIENT = False

try:
    import pyzmail
    HAS_PYZMAIL = True
except ImportError:
    HAS_PYZMAIL = False

logger = logging.getLogger(__name__)


class DocParseTool(BaseTool):
    """Tool for parsing documents."""

    @property
    def name(self) -> str:
        return "doc_parser"

    @property
    def description(self) -> str:
        return "Parses documents and extracts text content"

    def run(self, input_data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a document file, including email attachments, or fetch from email server.

        Args:
            input_data: Dictionary containing 'file_path' or email server config
            context: Execution context

        Returns:
            Dictionary with parsed content and metadata
        """
        try:
            # Check if we should fetch from email server
            email_config = input_data.get('email_config')
            if email_config:
                return self._fetch_and_parse_emails(email_config)

            # Otherwise, parse local file
            file_path = input_data.get('file_path')
            if not file_path:
                raise ValueError("file_path parameter is required")

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            file_type = self._detect_file_type(file_path)
            logger.info(f"Detected file type: {file_type} for {file_path}")

            if file_type == 'email':
                return self._parse_email(file_path)
            elif file_type == 'pdf':
                return self._parse_pdf(file_path)
            else:
                # Default text parsing
                return self._parse_text(file_path)

        except Exception as e:
            logger.error(f"Document parsing failed: {e}")
            raise

    def _detect_file_type(self, file_path: str) -> str:
        """Detect the file type based on extension and content."""
        # Check extension first
        _, ext = os.path.splitext(file_path.lower())

        if ext in ['.eml', '.msg']:
            return 'email'
        elif ext == '.pdf':
            return 'pdf'
        elif ext in ['.txt', '.md', '.csv']:
            return 'text'

        # Use magic if available for content-based detection
        if HAS_MAGIC:
            try:
                mime_type = magic.from_file(file_path, mime=True)
                if mime_type == 'message/rfc822':
                    return 'email'
                elif mime_type == 'application/pdf':
                    return 'pdf'
                elif mime_type.startswith('text/'):
                    return 'text'
            except Exception:
                pass

        # Fallback to mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type == 'message/rfc822':
            return 'email'
        elif mime_type == 'application/pdf':
            return 'pdf'

        return 'text'  # Default

    def _parse_email(self, file_path: str) -> Dict[str, Any]:
        """Parse email file and extract attachments."""
        with open(file_path, 'rb') as f:
            msg = BytesParser(policy=policy.default).parse(f)

        # Extract email metadata
        subject = msg.get('subject', 'No Subject')
        sender = msg.get('from', 'Unknown')
        recipients = msg.get('to', 'Unknown')
        date = msg.get('date', 'Unknown')

        # Extract body text
        body_text = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    body_text += part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            if msg.get_content_type() == 'text/plain':
                body_text = msg.get_payload(decode=True).decode('utf-8', errors='ignore')

        # Extract attachments
        attachments = []
        extracted_contracts = []

        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_disposition() == 'attachment':
                    filename = part.get_filename()
                    if filename:
                        # Save attachment
                        attachment_path = self._save_attachment(part, filename, file_path)
                        attachments.append({
                            'filename': filename,
                            'path': attachment_path,
                            'size': len(part.get_payload(decode=True))
                        })

                        # If it's a contract document, parse it
                        if self._is_contract_file(filename):
                            logger.info(f"Found contract attachment: {filename}")
                            contract_content = self._parse_attachment_content(part, filename)
                            if contract_content:
                                logger.info(f"Successfully parsed contract content from {filename}")
                                extracted_contracts.append({
                                    'filename': filename,
                                    'content': contract_content
                                })
                            else:
                                logger.warning(f"Failed to parse contract content from {filename}, but file was saved")
                                # Still count it as a contract even if parsing failed
                                extracted_contracts.append({
                                    'filename': filename,
                                    'content': f"[Content parsing failed for {filename}]",
                                    'parsing_failed': True
                                })

        return {
            'type': 'email',
            'subject': subject,
            'sender': sender,
            'recipients': recipients,
            'date': date,
            'body': body_text,
            'attachments': attachments,
            'contracts': extracted_contracts,
            'main_content': body_text + '\n\n' + '\n\n'.join([c['content'] for c in extracted_contracts])
        }

    def _parse_pdf(self, file_path: str) -> Dict[str, Any]:
        """Parse PDF file and extract text."""
        if not HAS_PYPDF2:
            raise ImportError("PyPDF2 is required for PDF parsing. Install with: pip install PyPDF2")

        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"

        return {
            'type': 'pdf',
            'content': text,
            'pages': len(pdf_reader.pages),
            'main_content': text
        }

    def _parse_text(self, file_path: str) -> Dict[str, Any]:
        """Parse plain text file."""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        return {
            'type': 'text',
            'content': content,
            'main_content': content
        }

    def _save_attachment(self, part, filename: str, email_path: str) -> str:
        """Save email attachment to disk."""
        # Create attachments directory
        email_dir = Path(email_path).parent
        attachments_dir = email_dir / "attachments"
        attachments_dir.mkdir(exist_ok=True)

        # Generate unique filename
        base_name = Path(filename).stem
        ext = Path(filename).suffix
        counter = 1
        attachment_path = attachments_dir / filename

        while attachment_path.exists():
            attachment_path = attachments_dir / f"{base_name}_{counter}{ext}"
            counter += 1

        # Save attachment
        with open(attachment_path, 'wb') as f:
            f.write(part.get_payload(decode=True))

        return str(attachment_path)

    def _is_contract_file(self, filename: str) -> bool:
        """Check if file is likely a contract document."""
        # English keywords
        contract_keywords = [
            'contract', 'agreement', 'treaty', 'pact', 'deal', 
            'offer', 'proposal', 'terms', 'nda', 'mou'
        ]
        
        # Chinese keywords (contract-related)
        chinese_keywords = [
            '合同',      # contract
            '协议',      # agreement  
            '劳动合同',  # labor contract
            '聘用',      # employment/hire
            '录用',      # offer/hire
            '要约'       # offer
        ]
        
        filename_lower = filename.lower()
        
        # Check English keywords
        if any(keyword in filename_lower for keyword in contract_keywords):
            return True
        
        # Check Chinese keywords (original filename, not lowercased)
        if any(keyword in filename for keyword in chinese_keywords):
            return True
            
        return False

    def _parse_attachment_content(self, part, filename: str) -> Optional[str]:
        """Parse content of email attachment."""
        try:
            content = part.get_payload(decode=True)

            # Handle different attachment types
            if filename.lower().endswith('.pdf') and HAS_PYPDF2:
                # Parse PDF attachment
                import io
                pdf_file = io.BytesIO(content)
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
            elif filename.lower().endswith(('.txt', '.md')):
                # Parse text attachment
                return content.decode('utf-8', errors='ignore')
            else:
                # Try to decode as text
                return content.decode('utf-8', errors='ignore')

        except Exception as e:
            logger.warning(f"Failed to parse attachment {filename}: {e}")
            return None

    def _fetch_and_parse_emails(self, email_config: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch emails from server and parse contracts."""
        if not HAS_IMAPCLIENT:
            raise ImportError("imapclient is required for email server access. Install with: pip install imapclient")

        server = email_config.get('server')
        port = int(email_config.get('port', 993))
        username = email_config.get('username')
        password = email_config.get('password')
        mailbox = email_config.get('mailbox', 'INBOX')
        search_criteria = email_config.get('search_criteria', 'UNSEEN')
        max_emails = int(email_config.get('max_emails', 10))

        if not all([server, username, password]):
            raise ValueError("Email config must include server, username, and password")

        logger.info(f"Connecting to email server: {server}:{port}")

        try:
            # Connect to IMAP server with SSL context
            import ssl
            ssl_context = ssl.create_default_context()
            # For development/testing, disable certificate verification if needed
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            client = IMAPClient(server, port=port, use_uid=True, ssl_context=ssl_context)
            client.login(username, password)
            client.select_folder(mailbox)

            # Search for emails
            messages = client.search(search_criteria)
            logger.info(f"Found {len(messages)} emails matching criteria: {search_criteria}")

            # Limit number of emails to process
            messages = messages[-max_emails:] if len(messages) > max_emails else messages

            processed_emails = []
            all_contracts = []

            for msg_id in messages:
                try:
                    # Fetch email
                    raw_message = client.fetch([msg_id], ['RFC822'])[msg_id][b'RFC822']
                    msg = BytesParser(policy=policy.default).parsebytes(raw_message)

                    # Parse email
                    email_data = self._parse_email_from_bytes(msg, msg_id)

                    if email_data['contracts']:
                        processed_emails.append(email_data)
                        all_contracts.extend(email_data['contracts'])

                    # Mark as read (optional)
                    if email_config.get('mark_as_read', False):
                        client.add_flags([msg_id], [b'\\Seen'])

                except Exception as e:
                    logger.warning(f"Failed to process email {msg_id}: {e}")
                    continue

            client.logout()

            # Combine all contract content
            combined_content = ""
            for contract in all_contracts:
                combined_content += f"\n--- Contract: {contract['filename']} ---\n"
                combined_content += contract['content'] + "\n"

            return {
                'type': 'email_server',
                'server': server,
                'emails_processed': len(processed_emails),
                'contracts_found': len(all_contracts),
                'emails': processed_emails,
                'contracts': all_contracts,
                'main_content': combined_content
            }

        except Exception as e:
            error_msg = str(e)
            if "AUTHENTICATIONFAILED" in error_msg:
                detailed_error = (
                    "Email authentication failed. Please check:\n"
                    "1. For Gmail: Use App Password instead of regular password\n"
                    "   Setup: https://support.google.com/accounts/answer/185833\n"
                    "2. Verify EMAIL_USERNAME and EMAIL_PASSWORD in .env file\n"
                    "3. Enable 2-factor authentication if required by your provider\n"
                    "4. Check if the account has IMAP access enabled"
                )
                logger.error(f"Email authentication failed: {detailed_error}")
                raise ValueError(detailed_error) from e
            elif "LOGIN" in error_msg.upper():
                detailed_error = (
                    "Email login failed. Please verify:\n"
                    "1. EMAIL_USERNAME is correct\n"
                    "2. EMAIL_PASSWORD is correct (use App Password for Gmail)\n"
                    "3. Account has IMAP access enabled\n"
                    "4. Check .env file exists and is properly configured"
                )
                logger.error(f"Email login failed: {detailed_error}")
                raise ValueError(detailed_error) from e
            else:
                logger.error(f"Email server connection failed: {e}")
                raise

    def _parse_email_from_bytes(self, msg, msg_id) -> Dict[str, Any]:
        """Parse email from bytes and extract attachments."""
        # Extract email metadata
        subject = msg.get('subject', 'No Subject')
        sender = msg.get('from', 'Unknown')
        recipients = msg.get('to', 'Unknown')
        date = msg.get('date', 'Unknown')

        # Extract body text
        body_text = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    body_text += part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            if msg.get_content_type() == 'text/plain':
                body_text = msg.get_payload(decode=True).decode('utf-8', errors='ignore')

        # Extract attachments
        attachments = []
        extracted_contracts = []

        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_disposition() == 'attachment':
                    filename = part.get_filename()
                    if filename:
                        # Save attachment with unique path based on message ID
                        attachment_path = self._save_attachment_from_server(part, filename, msg_id)
                        attachments.append({
                            'filename': filename,
                            'path': attachment_path,
                            'size': len(part.get_payload(decode=True))
                        })

                        # If it's a contract document, parse it
                        if self._is_contract_file(filename):
                            logger.info(f"Found contract attachment: {filename}")
                            contract_content = self._parse_attachment_content(part, filename)
                            if contract_content:
                                logger.info(f"Successfully parsed contract content from {filename}")
                                extracted_contracts.append({
                                    'filename': filename,
                                    'content': contract_content
                                })
                            else:
                                logger.warning(f"Failed to parse contract content from {filename}, but file was saved")
                                # Still count it as a contract even if parsing failed
                                extracted_contracts.append({
                                    'filename': filename,
                                    'content': f"[Content parsing failed for {filename}]",
                                    'parsing_failed': True
                                })

        return {
            'message_id': msg_id,
            'subject': subject,
            'sender': sender,
            'recipients': recipients,
            'date': date,
            'body': body_text,
            'attachments': attachments,
            'contracts': extracted_contracts,
            'main_content': body_text + '\n\n' + '\n\n'.join([c['content'] for c in extracted_contracts])
        }

    def _save_attachment_from_server(self, part, filename: str, msg_id) -> str:
        """Save email attachment from server to disk."""
        # Create attachments directory
        attachments_dir = Path("email_attachments")
        attachments_dir.mkdir(exist_ok=True)

        # Generate unique filename with message ID
        base_name = Path(filename).stem
        ext = Path(filename).suffix
        unique_filename = f"{msg_id}_{base_name}{ext}"
        attachment_path = attachments_dir / unique_filename

        # Handle filename conflicts
        counter = 1
        while attachment_path.exists():
            unique_filename = f"{msg_id}_{base_name}_{counter}{ext}"
            attachment_path = attachments_dir / unique_filename
            counter += 1

        # Save attachment
        with open(attachment_path, 'wb') as f:
            f.write(part.get_payload(decode=True))

        return str(attachment_path)
