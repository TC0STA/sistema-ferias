(() => {
  const close = modal => { modal.hidden = true; document.body.classList.remove('user-modal-open'); };
  const open = modal => { modal.hidden = false; document.body.classList.add('user-modal-open'); };
  document.querySelectorAll('[data-open]').forEach(button => button.addEventListener('click', () => open(document.getElementById(button.dataset.open))));
  document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => close(button.closest('.term-modal'))));

  function syncUser(select) {
    const form = select.form;
    const option = select.selectedOptions[0];
    if (!option || !option.value) return;
    ['nome', 'usuario', 'email'].forEach(name => { form.elements[name].value = option.dataset[name] || ''; });
    form.elements.perfil.value = option.dataset.perfil || '';
    form.elements.perfil_display.value = option.dataset.perfil || '';
  }
  document.querySelectorAll('[data-user-select]').forEach(select => select.addEventListener('change', () => syncUser(select)));

  const editModal = document.getElementById('editTermination');
  document.querySelectorAll('[data-edit]').forEach(button => button.addEventListener('click', () => {
    const data = JSON.parse(button.dataset.edit);
    const form = editModal.querySelector('form');
    form.action = `/desligamentos/${data.id}/editar`;
    Object.entries(data).forEach(([name, value]) => { if (form.elements[name]) form.elements[name].value = value ?? ''; });
    form.elements.perfil_display.value = data.perfil || '';
    open(editModal);
  }));

  const confirmModal = document.getElementById('confirmTermination');
  document.querySelectorAll('[data-confirm-action]').forEach(button => button.addEventListener('click', () => {
    const cancel = button.dataset.confirmKind === 'cancel';
    confirmModal.querySelector('form').action = button.dataset.confirmAction;
    document.getElementById('confirmTitle').textContent = cancel ? 'Cancelar solicitação?' : 'Confirmar desativação?';
    document.getElementById('confirmMessage').textContent = cancel ? 'A solicitação permanecerá no histórico como Cancelada.' : `O usuário ${button.dataset.confirmUser} será marcado como inativo no sistema Fokus Férias.`;
    const submit = document.getElementById('confirmSubmit');
    submit.textContent = cancel ? 'Confirmar cancelamento' : 'Confirmar desativação';
    open(confirmModal);
  }));
})();
