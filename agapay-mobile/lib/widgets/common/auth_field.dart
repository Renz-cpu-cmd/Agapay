import '../../core/ui.dart';

class AuthField extends StatelessWidget {
  const AuthField(
    this.label, {
    required this.controller,
    required this.hint,
    this.keyboardType,
    this.password = false,
    super.key,
  });
  final String label, hint;
  final TextEditingController controller;
  final TextInputType? keyboardType;
  final bool password;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      tx(
        label.toUpperCase(),
        size: 11,
        color: AppColors.label,
        weight: 600,
        display: true,
        spacing: 1.1,
      ),
      const SizedBox(height: 6),
      TextField(
        textAlignVertical: TextAlignVertical.center,
        controller: controller,
        obscureText: password,
        enableSuggestions: !password,
        autocorrect: false,
        keyboardType: keyboardType,
        textInputAction: TextInputAction.next,
        style: const TextStyle(
          fontFamily: 'Inter',
          fontSize: 14,
          fontWeight: FontWeight.w400,
          height: 20 / 14,
          color: AppColors.text,
        ),
        decoration: InputDecoration(
          constraints: const BoxConstraints(minHeight: 46),
          hintText: hint,
          semanticCounterText: label,
        ),
      ),
    ],
  );
}

const barangays = [
  'San Vicente',
  'Nancamaliran',
  'Catablan',
  'Tulong',
  'Pinmaludpod',
  'Poblacion',
  'Anonas',
];

class BarangayPicker extends StatelessWidget {
  const BarangayPicker({
    required this.value,
    required this.onChanged,
    super.key,
  });
  final String value;
  final ValueChanged<String> onChanged;
  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      return MenuAnchor(
        style: MenuStyle(
          backgroundColor: const WidgetStatePropertyAll(Color(0xff111d33)),
          surfaceTintColor: const WidgetStatePropertyAll(Colors.transparent),
          padding: const WidgetStatePropertyAll(EdgeInsets.zero),
          shape: WidgetStatePropertyAll(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: const BorderSide(color: AppColors.border),
            ),
          ),
          minimumSize: WidgetStatePropertyAll(Size(constraints.maxWidth, 0)),
          maximumSize: WidgetStatePropertyAll(Size(constraints.maxWidth, 300)),
          alignment: Alignment.bottomLeft,
        ),
        alignmentOffset: const Offset(0, 4),
        menuChildren: [
          for (final name in barangays)
            MenuItemButton(
              onPressed: () => onChanged(name),
              style: ButtonStyle(
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                fixedSize: WidgetStatePropertyAll(
                  Size(constraints.maxWidth, 40),
                ),
                padding: const WidgetStatePropertyAll(
                  EdgeInsets.symmetric(horizontal: 16),
                ),
                minimumSize: WidgetStatePropertyAll(
                  Size(constraints.maxWidth, 40),
                ),
              ),
              child: tx(name),
            ),
        ],
        builder: (context, controller, child) => Semantics(
          label: 'Barangay',
          button: true,
          child: InkWell(
            onTap: () {
              FocusManager.instance.primaryFocus?.unfocus();
              controller.isOpen ? controller.close() : controller.open();
            },
            borderRadius: BorderRadius.circular(12),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: AppColors.surface,
                border: Border.all(color: AppColors.border),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  tx(value, height: 20 / 14),
                  const SvgIcon('down', size: 14, color: AppColors.text),
                ],
              ),
            ),
          ),
        ),
      );
    },
  );
}
