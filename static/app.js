const app = Vue.createApp({
    data() {
        return {
            newQuote: {
                text: '',
                author: '',
                public: false,
                disableComments: false
            },
            quotes: []
        };
    },
    methods: {
        addQuote() {
            fetch('/api/add_quote', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(this.newQuote)
            })
            .then(response => response.json())
            .then(data => {
                window.location.href = '/quotes'; 
                if (!data.success) {
                    alert('Issue creating new post. ' + (data.error || 'Unknown error'));
                }
            })
            .catch(error => {
                window.location.href = '/quotes'; 
                console.error('Error adding quote:', error);
                alert('Issues encountered while creating new post. Please check the quotes page for confirmation.');
            });
        }
    }
}).mount('#app');