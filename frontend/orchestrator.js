class OpenLovableOrchestrator {
    constructor() {
        this.baseUrl = 'http://localhost:8000';
        this.chatMessages = document.getElementById('chat-messages');
        this.userInput = document.getElementById('user-input');
        this.sendBtn = document.getElementById('send-btn');
        
        this.initializeEventListeners();
        this.addMessage('ai', 'Hello! I\'m OpenLovable, your AI orchestrator. I can help you with emails, PDFs, and web searches. How can I assist you today?');
    }

    initializeEventListeners() {
        // Chat functionality
        this.sendBtn.addEventListener('click', () => this.handleSendMessage());
        this.userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleSendMessage();
            }
        });

        // Gmail functionality
        document.getElementById('compose-email-btn').addEventListener('click', () => {
            document.getElementById('email-form').classList.toggle('hidden');
        });
        document.getElementById('send-email-btn').addEventListener('click', () => this.handleSendEmail());

        // PDF functionality
        this.initializePDFUpload();
        document.getElementById('ask-pdf-btn').addEventListener('click', () => this.handlePDFQuestion());

        // Web search functionality
        document.getElementById('search-web-btn').addEventListener('click', () => this.handleWebSearch());
    }

    addMessage(sender, text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        messageDiv.textContent = text;
        this.chatMessages.appendChild(messageDiv);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    async handleSendMessage() {
        const message = this.userInput.value.trim();
        if (!message) return;

        this.addMessage('user', message);
        this.userInput.value = '';

        // Simple command parsing
        if (message.startsWith('/email')) {
            const task = message.replace('/email', '').trim();
            this.handleEmailCommand(task);
        } else if (message.startsWith('/pdf')) {
            const question = message.replace('/pdf', '').trim();
            this.handlePDFCommand(question);
        } else if (message.startsWith('/search')) {
            const query = message.replace('/search', '').trim();
            this.handleSearchCommand(query);
        } else {
            // General orchestrator request - use web search for general queries
            await this.handleWebSearch(message);
        }
    }

    async handleEmailCommand(task) {
        this.addMessage('ai', 'I\'ll help you compose an email. Please provide the recipient email address.');
        // This would open the email form with pre-filled task
        document.getElementById('email-task').value = task;
        document.getElementById('email-form').classList.remove('hidden');
    }

    async handleSendEmail() {
        const to = document.getElementById('email-to').value;
        const task = document.getElementById('email-task').value;
        const tone = document.getElementById('email-tone').value;

        if (!to || !task) {
            this.addMessage('ai', 'Please provide recipient email and task description.');
            return;
        }

        try {
            const response = await fetch(`${this.baseUrl}/gmail/send`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    task: task, 
                    to: [to], 
                    tone: tone,
                    cc: [],
                    bcc: []
                })
            });

            const data = await response.json();
            if (data.success) {
                this.addMessage('ai', `✅ Email sent successfully! Preview: ${JSON.stringify(data.email_preview)}`);
                document.getElementById('email-form').classList.add('hidden');
            } else {
                this.addMessage('ai', `❌ Error: ${data.detail || data.error}`);
            }
        } catch (error) {
            this.addMessage('ai', `❌ Error sending email: ${error.message}`);
        }
    }

    initializePDFUpload() {
        const uploadZone = document.getElementById('pdf-upload-zone');
        const fileInput = document.getElementById('pdf-file');

        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });

        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('dragover');
        });

        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            this.handlePDFUpload(e.dataTransfer.files);
        });

        fileInput.addEventListener('change', (e) => {
            this.handlePDFUpload(e.target.files);
        });
    }

    async handlePDFUpload(files) {
        const formData = new FormData();
        for (let file of files) {
            formData.append('file', file);
        }

        try {
            const response = await fetch(`${this.baseUrl}/api/upload`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            if (data.success) {
                this.addMessage('ai', `✅ PDFs uploaded successfully! You can now ask questions about them.`);
                document.getElementById('pdf-question').classList.remove('hidden');
                this.displayUploadedFiles([{filename: data.filename}]);
            }
        } catch (error) {
            this.addMessage('ai', `❌ Error uploading PDFs: ${error.message}`);
        }
    }

    displayUploadedFiles(files) {
        const container = document.getElementById('uploaded-pdfs');
        container.innerHTML = '';
        files.forEach(file => {
            const div = document.createElement('div');
            div.className = 'uploaded-file';
            div.textContent = file.filename;
            container.appendChild(div);
        });
    }

    async handlePDFQuestion() {
        const question = document.getElementById('pdf-query').value;
        if (!question) return;

        try {
            const response = await fetch(`${this.baseUrl}/api/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question, max_results: 5 })
            });

            const data = await response.json();
            this.addMessage('ai', data.response || data.detail);
        } catch (error) {
            this.addMessage('ai', `❌ Error searching PDF: ${error.message}`);
        }
    }

    async handleWebSearch(query = null) {
        const searchQuery = query || document.getElementById('web-query').value;
        if (!searchQuery) return;

        if (!query) {
            this.addMessage('user', `🔍 Web search: ${searchQuery}`);
            document.getElementById('web-query').value = '';
        }

        // Add typing indicator
        const typingIndicator = this.addTypingIndicator();
        
        try {
            const response = await fetch(`${this.baseUrl}/agent/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: searchQuery, max_results: 5 })
            });

            // Remove typing indicator
            if (typingIndicator) {
                this.chatMessages.removeChild(typingIndicator);
            }

            const data = await response.json();
            if (data.success) {
                // Format the search results better
                let formattedResults = this.formatSearchResults(data.result || data.results);
                this.addMessage('ai', `🔍 **Search Results for "${searchQuery}"**\n\n${formattedResults}`);
                
                // Add to search history
                this.addToSearchHistory(searchQuery);
            } else {
                this.addMessage('ai', `❌ **Search Failed**\n${data.error || 'Unknown error occurred'}`);
            }
        } catch (error) {
            // Remove typing indicator on error
            if (typingIndicator) {
                this.chatMessages.removeChild(typingIndicator);
            }
            this.addMessage('ai', `❌ **Network Error**\nCould not connect to search service: ${error.message}`);
        }
    }

    addTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message ai-message typing-indicator';
        typingDiv.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
        this.chatMessages.appendChild(typingDiv);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        return typingDiv;
    }

    formatSearchResults(result) {
        if (Array.isArray(result)) {
            return result.map((item, index) => `**${index + 1}.** ${item}`).join('\n\n');
        }
        
        // Clean up CrewAI output formatting
        let formatted = String(result)
            .replace(/\\n/g, '\n')
            .replace(/\\"/g, '"')
            .replace(/\*\*/g, '**')
            .trim();
            
        // Add bullet points if not already formatted
        if (!formatted.includes('•') && !formatted.includes('-')) {
            const lines = formatted.split('\n').filter(line => line.trim());
            if (lines.length > 1) {
                formatted = lines.map(line => `• ${line.trim()}`).join('\n');
            }
        }
        
        return formatted;
    }

    addToSearchHistory(query) {
        let history = JSON.parse(localStorage.getItem('searchHistory') || '[]');
        history = history.filter(item => item !== query); // Remove duplicates
        history.unshift(query); // Add to beginning
        history = history.slice(0, 10); // Keep only last 10 searches
        localStorage.setItem('searchHistory', JSON.stringify(history));
        this.updateSearchHistoryUI();
    }

    updateSearchHistoryUI() {
        const history = JSON.parse(localStorage.getItem('searchHistory') || '[]');
        const historyContainer = document.getElementById('search-history');
        if (historyContainer) {
            historyContainer.innerHTML = history.length > 0 
                ? history.map(item => `<div class="history-item" onclick="document.getElementById('web-query').value='${item.replace(/'/g, "\\'")}'; document.getElementById('search-web-btn').click();">${item}</div>`).join('')
                : '<div class="no-history">No recent searches</div>';
        }
    }

    async handlePDFCommand(question) {
        if (!question) {
            this.addMessage('ai', 'Please upload a PDF first, then ask your question.');
            return;
        }
        document.getElementById('pdf-query').value = question;
        await this.handlePDFQuestion();
    }

    async handleSearchCommand(query) {
        document.getElementById('web-query').value = query;
        await this.handleWebSearch(query);
    }
}

// Initialize the orchestrator when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new OpenLovableOrchestrator();
});
