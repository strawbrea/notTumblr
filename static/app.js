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
                console.log('Response received:', data);
                if (data.success) {
                    console.log('Redirecting to /quotes');
                    window.location.href = '/quotes'; // Ensure this is the correct URL
                } else {
                    console.log('Error:', data.error);
                    alert('Issues adding quote. Please try again. ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Issues adding quote. Please try again.');
            });
        }
    }
}).mount('#app');