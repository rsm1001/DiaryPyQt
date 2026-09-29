import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_file_dialog/flutter_file_dialog.dart';

class DiaryDocumentAdapter {
  const DiaryDocumentAdapter();

  Future<String?> pickJson() async {
    final path = await FlutterFileDialog.pickFile(
      params: const OpenFileDialogParams(
        fileExtensionsFilter: ['json'],
        mimeTypesFilter: ['application/json', 'text/plain'],
      ),
    );
    if (path == null) return null;
    final file = File(path);
    if (await file.length() > 5 * 1024 * 1024) {
      throw const FormatException('Diary file exceeds 5 MB');
    }
    return file.readAsString(encoding: utf8);
  }

  Future<bool> saveJson(String data) async {
    final name =
        'diary-export-${DateTime.now().toIso8601String().substring(0, 10)}.json';
    final target = await FlutterFileDialog.saveFile(
      params: SaveFileDialogParams(
        data: Uint8List.fromList(utf8.encode(data)),
        fileName: name,
        mimeTypesFilter: const ['application/json'],
      ),
    );
    return target != null;
  }
}
