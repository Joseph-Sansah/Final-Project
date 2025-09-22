document.addEventListener('DOMContentLoaded', () => {
    const questionsDiv = document.getElementById('questions');
    const addBtn = document.getElementById('add-question');

    addBtn.addEventListener('click', () => {
        const index = questionsDiv.children.length;
        const questionBlock = `
            <div class="question-block">
                <label>Question:</label>
                <input type="text" name="questions[${index}][text]" placeholder="Enter question" required>

                <label>Options:</label>
                <input type="text" name="questions[${index}][option1]" placeholder="Option 1" required>
                <input type="text" name="questions[${index}][option2]" placeholder="Option 2" required>
                <input type="text" name="questions[${index}][option3]" placeholder="Option 3">
                <input type="text" name="questions[${index}][option4]" placeholder="Option 4">

                <label>Correct Answer:</label>
                <select name="questions[${index}][answer]">
                    <option value="option1">Option 1</option>
                    <option value="option2">Option 2</option>
                    <option value="option3">Option 3</option>
                    <option value="option4">Option 4</option>
                </select>
            </div>
        `;
        questionsDiv.insertAdjacentHTML('beforeend', questionBlock);
    });
});
