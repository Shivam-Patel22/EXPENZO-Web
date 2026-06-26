class CustomCalendar {
  constructor(inputElement) {
    this.originalInput = inputElement;
    
    // Create the display input (what the user actually clicks)
    this.displayInput = document.createElement('input');
    this.displayInput.type = 'text';
    this.displayInput.className = this.originalInput.className + ' custom-date-display';
    this.displayInput.placeholder = this.originalInput.placeholder || 'Select Date';
    this.displayInput.readOnly = true;
    
    // Hide original input but keep it in DOM for form submission
    this.originalInput.style.display = 'none';
    this.originalInput.type = 'text'; // change type so browser doesn't show native icon if unhidden
    this.originalInput.parentNode.insertBefore(this.displayInput, this.originalInput.nextSibling);

    this.currentDate = new Date();
    this.selectedDate = null;
    
    this.isDayOnly = this.originalInput.dataset.dayOnly === 'true';

    // Init dates
    if (this.isDayOnly) {
      if (this.originalInput.value) {
        this.selectedDate = null;
      }
    } else {
      if (this.originalInput.value) {
        const parsed = new Date(this.originalInput.value);
        if (!isNaN(parsed)) {
          this.selectedDate = parsed;
          this.currentDate = new Date(parsed);
        }
      } else {
        this.selectedDate = new Date();
      }
    }
    
    this.updateDisplayInput();
    this.buildPopup();
    this.bindEvents();
  }

  buildPopup() {
    this.popup = document.createElement('div');
    this.popup.className = 'custom-calendar-popup';
    if (this.isDayOnly) {
      this.popup.classList.add('day-only-mode');
    }
    this.popup.innerHTML = `
      <div class="calendar-header">
        <button type="button" class="calendar-nav-btn prev-btn">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
        </button>
        <div class="calendar-month-year"></div>
        <button type="button" class="calendar-nav-btn next-btn">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
        </button>
      </div>
      <div class="calendar-weekdays">
        <div class="calendar-weekday">MON</div>
        <div class="calendar-weekday">TUE</div>
        <div class="calendar-weekday">WED</div>
        <div class="calendar-weekday">THU</div>
        <div class="calendar-weekday">FRI</div>
        <div class="calendar-weekday">SAT</div>
        <div class="calendar-weekday">SUN</div>
      </div>
      <div class="calendar-days"></div>
    `;

    // Append to wrapper or parent
    const wrapper = document.createElement('div');
    wrapper.style.position = 'relative';
    wrapper.style.width = '100%';
    this.originalInput.parentNode.insertBefore(wrapper, this.displayInput);
    wrapper.appendChild(this.displayInput);
    wrapper.appendChild(this.originalInput);
    wrapper.appendChild(this.popup);

    this.monthYearDisplay = this.popup.querySelector('.calendar-month-year');
    this.daysGrid = this.popup.querySelector('.calendar-days');
  }

  bindEvents() {
    this.displayInput.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggle();
    });

    this.popup.querySelector('.prev-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      this.currentDate.setMonth(this.currentDate.getMonth() - 1);
      this.render();
    });

    this.popup.querySelector('.next-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      this.currentDate.setMonth(this.currentDate.getMonth() + 1);
      this.render();
    });

    this.popup.addEventListener('click', (e) => {
      e.stopPropagation(); // Keep open when clicking inside
    });

    document.addEventListener('click', () => {
      this.close();
    });
  }

  formatDateStr(dateObj) {
    const yyyy = dateObj.getFullYear();
    const mm = String(dateObj.getMonth() + 1).padStart(2, '0');
    const dd = String(dateObj.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  }

  updateDisplayInput() {
    if (this.isDayOnly) {
      if (this.originalInput.value) {
        this.displayInput.value = "Day " + this.originalInput.value;
      }
    } else {
      if (this.selectedDate) {
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        this.displayInput.value = `${months[this.selectedDate.getMonth()]} ${this.selectedDate.getDate()}, ${this.selectedDate.getFullYear()}`;
        this.originalInput.value = this.formatDateStr(this.selectedDate);
      }
    }
  }

  toggle() {
    if (this.popup.classList.contains('active')) {
      this.close();
    } else {
      this.open();
    }
  }

  open() {
    // Close other calendars
    document.querySelectorAll('.custom-calendar-popup.active').forEach(p => p.classList.remove('active'));
    if (this.selectedDate) {
      this.currentDate = new Date(this.selectedDate);
    } else {
      this.currentDate = new Date();
    }
    this.render();

    // Auto-position logic
    this.popup.style.visibility = 'hidden';
    this.popup.classList.add('active');
    
    const rect = this.displayInput.getBoundingClientRect();
    const popupHeight = this.popup.offsetHeight;
    const spaceAbove = rect.top;
    
    this.popup.classList.remove('open-down');
    if (spaceAbove < popupHeight + 10 && (window.innerHeight - rect.bottom) > spaceAbove) {
      this.popup.classList.add('open-down');
    }
    
    this.popup.style.visibility = '';
  }

  close() {
    this.popup.classList.remove('active');
  }

  render() {
    if (this.isDayOnly) {
      if (this.monthYearDisplay) {
        this.monthYearDisplay.textContent = 'SELECT DAY';
        this.popup.querySelector('.prev-btn').style.visibility = 'hidden';
        this.popup.querySelector('.next-btn').style.visibility = 'hidden';
        this.popup.querySelector('.calendar-weekdays').style.display = 'none';
      }
      this.daysGrid.innerHTML = '';
      for (let i = 1; i <= 31; i++) {
        const dayEl = document.createElement('div');
        dayEl.className = 'calendar-day';
        dayEl.textContent = i;
        
        if (this.originalInput.value && parseInt(this.originalInput.value) === i) {
          dayEl.classList.add('selected');
        }
        
        dayEl.addEventListener('click', (e) => {
          e.stopPropagation();
          this.originalInput.value = i;
          this.updateDisplayInput();
          this.close();
          this.render();
        });
        
        this.daysGrid.appendChild(dayEl);
      }
      return;
    }

    const year = this.currentDate.getFullYear();
    const month = this.currentDate.getMonth();
    const monthsStr = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    
    this.monthYearDisplay.textContent = `${monthsStr[month]} ${year}`;
    this.daysGrid.innerHTML = '';

    const firstDay = new Date(year, month, 1).getDay();
    // Adjust so Monday is 0, Sunday is 6
    const startingDay = firstDay === 0 ? 6 : firstDay - 1; 
    
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const today = new Date();

    // Fill blank days
    for (let i = 0; i < startingDay; i++) {
      const blank = document.createElement('div');
      blank.className = 'calendar-day empty';
      this.daysGrid.appendChild(blank);
    }

    // Fill actual days
    for (let i = 1; i <= daysInMonth; i++) {
      const dayEl = document.createElement('div');
      dayEl.className = 'calendar-day';
      dayEl.textContent = i;
      
      const thisDate = new Date(year, month, i);

      if (year === today.getFullYear() && month === today.getMonth() && i === today.getDate()) {
        dayEl.classList.add('today');
      }

      if (this.selectedDate && 
          year === this.selectedDate.getFullYear() && 
          month === this.selectedDate.getMonth() && 
          i === this.selectedDate.getDate()) {
        dayEl.classList.add('selected');
      }

      dayEl.addEventListener('click', (e) => {
        e.stopPropagation();
        this.selectedDate = new Date(year, month, i);
        this.updateDisplayInput();
        this.close();
        this.render(); // Update selected visual
      });

      this.daysGrid.appendChild(dayEl);
    }
  }

  resetToOriginal() {
    // Called when the underlying form is reset
    setTimeout(() => {
      if (this.isDayOnly) {
        if (this.originalInput.value) {
          this.updateDisplayInput();
          this.render();
        }
      } else {
        if (this.originalInput.value) {
          const parsed = new Date(this.originalInput.value);
          if (!isNaN(parsed)) {
            this.selectedDate = parsed;
            this.currentDate = new Date(parsed);
            this.updateDisplayInput();
            this.render();
          }
        }
      }
    }, 10); // Small delay to let the form reset happen first
  }
}

// Global initialization
function initCustomCalendars() {
  document.querySelectorAll('input[type="date"], input[data-day-only="true"]').forEach(input => {
    if (!input.dataset.calendarInitialized) {
      input.customCalendar = new CustomCalendar(input);
      input.dataset.calendarInitialized = 'true';
    }
  });
}

document.addEventListener('DOMContentLoaded', initCustomCalendars);
